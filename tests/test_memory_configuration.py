from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


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


def test_memory_llm_route_survives_provisioning(tmp_path: Path) -> None:
    config = tmp_path / "agent_memory.yaml"
    original = (
        "other_section:\n  model_name: unrelated\n"
        "memory_optimization:\n"
        "  provider: ollama\n"
        "  server_url: http://old-host:11434\n"
        "  model_name: old-model\n"
        "  api_key: unchanged\n"
        '  user_facts:\n    extraction_model: ""\n'
        "next_section:\n  provider: unchanged\n"
    )
    config.write_text(original)
    _load_configurator().rewrite_llm_route(config)
    assert config.read_text() == (
        "other_section:\n  model_name: unrelated\n"
        "memory_optimization:\n"
        '  provider: "openai"\n'
        '  server_url: "http://127.0.0.1:4050"\n'
        '  model_name: "haru:canonical"\n'
        "  api_key: unchanged\n"
        '  user_facts:\n    extraction_model: ""\n'
        "next_section:\n  provider: unchanged\n"
    )
    first = config.read_text()
    _load_configurator().rewrite_llm_route(config)
    assert config.read_text() == first


@pytest.mark.parametrize(
    "body", ["provider: ollama", "  provider: ollama\n  provider: duplicate"]
)
def test_memory_llm_route_rejects_incomplete_config_without_writing(
    tmp_path: Path, body: str
) -> None:
    config = tmp_path / "agent_memory.yaml"
    original = "memory_optimization:\n" + body + "\n"
    config.write_text(original)
    with pytest.raises(ValueError):
        _load_configurator().rewrite_llm_route(config)
    assert config.read_text() == original
