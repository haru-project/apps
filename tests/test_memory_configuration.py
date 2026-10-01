from __future__ import annotations

import importlib.util
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _compose_with_fake_docker(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess:
    """Run the memory stack through scripts/compose.sh against a docker stub.

    The stub reports the arguments it was called with plus the MEMORY_LLM_* variables the wrapper
    exported. An unset one is reported as <unset>, which the compose file turns into the proxy
    endpoint, while an exported empty one keeps the mounted YAML — see docker-compose-memory.yaml.
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env bash
printf 'ARGS %s\n' "$*"
for name in PROVIDER SERVER_URL MODEL; do
    eval "value=\\${MEMORY_LLM_${name}-<unset>}"
    printf 'MEMORY_LLM_%s=%s\n' "${name}" "${value}"
done
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    for key in ("AGENT_MEMORY_LLM_BACKEND", "MEMORY_LLM_PROVIDER", "MEMORY_LLM_SERVER_URL"):
        environment.pop(key, None)
    environment.update(overrides)

    return subprocess.run(
        ["bash", str(ROOT / "scripts/compose.sh"), "memory", "config", "--services"],
        capture_output=True,
        encoding="utf-8",
        env=environment,
    )


def _load_configurator():
    path = ROOT / "scripts/configure_memory_data.py"
    spec = importlib.util.spec_from_file_location("configure_memory_data", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rewrite_weaviate_connection(tmp_path: Path) -> None:
    config = tmp_path / "agent_memory.yaml"
    config.write_text(
        "memory:\n"
        '  weaviate_host: "localhost"\n'
        "  weaviate_port: 8080\n"
        "  weaviate_grpc_port: 50051\n"
        "  memory_retention_days: 365\n",
        encoding="utf-8",
    )

    module = _load_configurator()
    module.rewrite_weaviate_connection(config, "127.0.0.1", "8082", "50052")

    assert config.read_text(encoding="utf-8") == (
        "memory:\n"
        '  weaviate_host: "127.0.0.1"\n'
        "  weaviate_port: 8082\n"
        "  weaviate_grpc_port: 50052\n"
        "  memory_retention_days: 365\n"
    )


def test_rewrite_rejects_unknown_config_shape(tmp_path: Path) -> None:
    config = tmp_path / "agent_memory.yaml"
    config.write_text("memory: {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="weaviate_host"):
        _load_configurator().rewrite_weaviate_connection(
            config, "localhost", "8082", "50052"
        )


def test_rewrite_rejects_duplicate_settings(tmp_path: Path) -> None:
    config = tmp_path / "agent_memory.yaml"
    config.write_text(
        "memory:\n"
        "  weaviate_host: localhost\n"
        "  weaviate_host: duplicate\n"
        "  weaviate_port: 8080\n"
        "  weaviate_grpc_port: 50051\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="found 2"):
        _load_configurator().rewrite_weaviate_connection(
            config, "localhost", "8082", "50052"
        )


@pytest.mark.parametrize("port", ["0", "65536", "not-a-port"])
def test_rewrite_rejects_invalid_ports(tmp_path: Path, port: str) -> None:
    config = tmp_path / "agent_memory.yaml"
    config.write_text(
        "memory:\n"
        "  weaviate_host: localhost\n"
        "  weaviate_port: 8080\n"
        "  weaviate_grpc_port: 50051\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        _load_configurator().rewrite_weaviate_connection(
            config, "localhost", port, "50052"
        )


def test_ollama_backend_starts_the_local_container_and_keeps_the_yaml_endpoint(
    tmp_path: Path,
) -> None:
    result = _compose_with_fake_docker(tmp_path, AGENT_MEMORY_LLM_BACKEND="ollama")

    assert result.returncode == 0, result.stderr
    assert "--profile memory-ollama" in result.stdout
    # Empty, so agent-memory keeps the mounted YAML endpoint (the bundled Ollama container).
    assert "MEMORY_LLM_PROVIDER=\n" in result.stdout
    assert "MEMORY_LLM_SERVER_URL=\n" in result.stdout


def test_litellm_backend_leaves_the_ollama_container_out_and_points_at_the_proxy(
    tmp_path: Path,
) -> None:
    # No override: this is what envs/memory.env selects, i.e. the deployment default.
    result = _compose_with_fake_docker(tmp_path)

    assert result.returncode == 0, result.stderr
    # No profile: the Ollama container is not part of the project, so it holds no GPU memory.
    assert "memory-ollama" not in result.stdout
    assert "MEMORY_LLM_PROVIDER=openai\n" in result.stdout
    # Left unset here on purpose; the compose file resolves both to the proxy endpoint, which
    # validate_compose.sh asserts against a real render.
    assert "MEMORY_LLM_SERVER_URL=<unset>\n" in result.stdout
    assert "MEMORY_LLM_MODEL=<unset>\n" in result.stdout


def test_unknown_memory_llm_backend_is_rejected(tmp_path: Path) -> None:
    result = _compose_with_fake_docker(tmp_path, AGENT_MEMORY_LLM_BACKEND="bedrock")

    assert result.returncode == 1
    assert "must be ollama or litellm" in result.stderr


def test_both_stacks_default_to_the_shared_litellm_backend() -> None:
    # The all-in-one stack has its own env file, and a disagreement there would include the
    # Ollama container in one stack and not the other.
    for env_file in ("envs/memory.env", "envs/all.env"):
        settings = (ROOT / env_file).read_text()
        assert "AGENT_MEMORY_LLM_BACKEND=litellm" in settings, env_file
        assert "AGENT_MEMORY_LITELLM_MODEL=haru:canonical" in settings, env_file


def test_backend_falls_back_to_litellm_when_nothing_sets_it() -> None:
    # Both shipped env files set it, so this guards the empty arm itself: an env file predating
    # the switch must not silently start the GPU container.
    assert 'litellm|"")' in (ROOT / "scripts/compose.sh").read_text()


def test_ollama_container_is_profile_gated_without_a_hard_dependency() -> None:
    # A depends_on pointing at a profile-gated service invalidates the whole project whenever
    # that profile is off, so agent-memory must not declare one; it retries the LLM endpoint.
    compose = (ROOT / "apps/docker-compose-memory.yaml").read_text()
    ollama_block = compose.split("  agent-memory-ollama:")[1].split("\n  agent-memory:")[0]
    assert 'profiles: ["memory-ollama"]' in ollama_block
    agent_block = compose.split("\n  agent-memory:")[1].split("\n  agent-memory-dashboard:")[0]
    dependencies = agent_block.split("depends_on:")[1].split("restart:")[0]
    assert "agent-memory-weaviate" in dependencies
    assert "agent-memory-ollama" not in dependencies


def test_empty_overrides_fall_back_to_the_mounted_yaml_not_the_proxy() -> None:
    # "-" and not ":-": compose.sh signals the ollama backend by exporting these empty, so a
    # ":-" default here would override the mounted YAML with the proxy endpoint anyway.
    agent_block = (
        (ROOT / "apps/docker-compose-memory.yaml")
        .read_text()
        .split("\n  agent-memory:")[1]
        .split("\n  agent-memory-dashboard:")[0]
    )
    for variable in ("MEMORY_LLM_PROVIDER", "MEMORY_LLM_SERVER_URL", "MEMORY_LLM_MODEL"):
        assert f'{variable}: "${{{variable}-' in agent_block, variable


def test_memory_is_torn_down_before_the_llm_proxy_it_depends_on() -> None:
    # agent-memory extracts the last session's facts while stopping, and with the litellm backend
    # that call goes to the llm stack. Tearing llm down first loses those facts silently.
    stacks = [
        line.split()[2]
        for line in (ROOT / "stop.sh").read_text().splitlines()
        if "scripts/compose.sh" in line
    ]
    assert stacks.index("reasoner") < stacks.index("memory") < stacks.index("llm")


def test_memory_shutdown_grace_covers_an_in_flight_extraction() -> None:
    # hybrid_memory_node waits up to 20 s for the fact writer; a shorter grace period SIGKILLs it.
    compose = (ROOT / "apps/docker-compose-memory.yaml").read_text()
    grace = re.search(r"stop_grace_period:\s*(\d+)s", compose)
    assert grace is not None
    assert int(grace.group(1)) >= 20
