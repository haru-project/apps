from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import stat
import subprocess

import pytest
from ruamel.yaml import YAML

from haru_configurator import configuration
from haru_configurator.configuration import (
    ConfigurationWriter,
    has_provider_secret,
    validate_compatibility,
)
from haru_configurator.models import Deployment, LLMProvider, SetupAnswers


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "apps").mkdir()
    (tmp_path / "config" / "behavior_trees").mkdir(parents=True)
    (tmp_path / "config" / "domain_bridge.yaml").write_text(
        "name: haru_domain_bridge\nfrom_domain: 200\nto_domain: 12\ntopics: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "envs").mkdir()
    (tmp_path / "data" / "speech" / "configs").mkdir(parents=True)
    (tmp_path / "apps" / "docker-compose-reasoner.yaml").write_text(
        "services:\n  bt-forest:\n    image: test\n", encoding="utf-8"
    )
    (tmp_path / "data" / "speech" / "configs" / "haru_speech.yaml").write_text(
        "/**/speech_stack:\n  ros__parameters:\n    sources:\n"
        "      - source_id: mic_0\n        enabled: false\n"
        "      - source_id: mic_1\n        enabled: true\n"
        "        capture_enabled: true\n        speech_enabled: true\n",
        encoding="utf-8",
    )
    return tmp_path


def test_writer_creates_local_physical_override_and_protects_secret(tmp_path, monkeypatch) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(configuration, "STACK_FILES", {"reasoner": "docker-compose-reasoner.yaml"})
    monkeypatch.setattr(
        configuration,
        "compatibility_payload",
        lambda _: {"schema_version": "3", "repo_revision": "test", "service_inventory": []},
    )
    answers = SetupAnswers(
        deployment=Deployment.PHYSICAL,
        robot_host="haru-19.local",
        llm_provider=LLMProvider.BEDROCK,
        llm_model_id="google.gemma-4-26b-a4b",
        kinect_transcription_enabled=False,
    )
    ConfigurationWriter(root).write(answers, "secret-value")

    local_env = (root / ".haru" / "local.env").read_text(encoding="utf-8")
    assert "ROS_DOMAIN_ID=19" in local_env
    assert "HARU_NLP_SERVER_GPU_ENABLED=true" in local_env
    assert "HARU_AGENT_MODEL_ID=haru:canonical" in local_env
    assert "BEDROCK_MANTLE_REGION=eu-central-1" in local_env
    assert "secret-value" not in local_env
    override = (root / ".haru" / "compose-reasoner.yaml").read_text(encoding="utf-8")
    assert "expressivity_controller.xml" not in override
    assert "simple_gaze_controller.xml" in override
    secret_path = root / "envs" / "llm.secrets.env"
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
    assert "BEDROCK_MANTLE_API_KEY=secret-value" in secret_path.read_text(encoding="utf-8")
    assert has_provider_secret(root, answers)

    yaml = YAML(typ="safe")
    speech = yaml.load((root / ".haru" / "haru_speech.yaml").read_text(encoding="utf-8"))
    kinect = speech["/**/speech_stack"]["ros__parameters"]["sources"][1]
    assert kinect["capture_enabled"] is False
    assert kinect["speech_enabled"] is False
    original = yaml.load(
        (root / "data" / "speech" / "configs" / "haru_speech.yaml").read_text(encoding="utf-8")
    )
    assert original["/**/speech_stack"]["ros__parameters"]["sources"][1]["speech_enabled"] is True


def test_simulator_override_does_not_mount_physical_trees(tmp_path, monkeypatch) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(configuration, "STACK_FILES", {"reasoner": "docker-compose-reasoner.yaml"})
    monkeypatch.setattr(
        configuration,
        "compatibility_payload",
        lambda _: {"schema_version": "3", "repo_revision": "test", "service_inventory": []},
    )
    ConfigurationWriter(root).write(SetupAnswers(deployment=Deployment.SIMULATOR))
    override = (root / ".haru" / "compose-reasoner.yaml").read_text(encoding="utf-8")
    assert "expressivity_controller.xml" not in override


def test_writer_generates_canonical_provider_and_domain_bridge(tmp_path, monkeypatch) -> None:
    root = _repo(tmp_path)
    (root / "apps" / "docker-compose-llm.yaml").write_text(
        "services:\n  server:\n    image: test\n", encoding="utf-8"
    )
    (root / "apps" / "docker-compose-domain-bridge.yaml").write_text(
        "services:\n  domain-bridge:\n    image: test\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        configuration,
        "STACK_FILES",
        {
            "llm": "docker-compose-llm.yaml",
            "domain-bridge": "docker-compose-domain-bridge.yaml",
        },
    )
    monkeypatch.setattr(
        configuration,
        "compatibility_payload",
        lambda _: {"schema_version": "3", "repo_revision": "test", "service_inventory": []},
    )
    answers = SetupAnswers(
        deployment=Deployment.PHYSICAL,
        robot_host="haru-19.local",
        llm_provider=LLMProvider.OPENAI,
    )
    ConfigurationWriter(root).write(answers, "openai-secret")

    provider = (root / ".haru" / "litellm_server.yaml").read_text(encoding="utf-8")
    assert "model_name: haru:canonical" in provider
    assert "model: openai/gpt-4.1" in provider
    bridge = YAML(typ="safe").load(
        (root / ".haru" / "domain_bridge.yaml").read_text(encoding="utf-8")
    )
    assert bridge["from_domain"] == 200
    assert bridge["to_domain"] == 19
    override = (root / ".haru" / "compose-domain-bridge.yaml").read_text(
        encoding="utf-8"
    )
    assert ".haru/domain_bridge.yaml:/shared/config/domain_bridge.yaml:ro" in override


@pytest.mark.parametrize(
    ("provider", "model", "expected", "api_base"),
    [
        (
            LLMProvider.BEDROCK,
            "google.gemma-4-26b-a4b",
            "bedrock_mantle/google.gemma-4-26b-a4b",
            None,
        ),
        (LLMProvider.OPENAI, "gpt-4.1", "openai/gpt-4.1", None),
        (
            LLMProvider.ANTHROPIC,
            "claude-sonnet-4-5",
            "anthropic/claude-sonnet-4-5",
            None,
        ),
        (
            LLMProvider.CUSTOM,
            "local-model",
            "openai/local-model",
            "http://model-host:8000/v1",
        ),
    ],
)
def test_provider_alternatives_preserve_canonical_alias(
    tmp_path, monkeypatch, provider, model, expected, api_base
) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(
        configuration, "STACK_FILES", {"reasoner": "docker-compose-reasoner.yaml"}
    )
    monkeypatch.setattr(
        configuration,
        "compatibility_payload",
        lambda _: {
            "schema_version": "3",
            "repo_revision": "test",
            "service_inventory": [],
        },
    )
    answers = SetupAnswers(
        deployment=Deployment.SIMULATOR,
        llm_provider=provider,
        llm_model_id=model,
        llm_api_base=api_base,
    )

    ConfigurationWriter(root).write(answers)

    config = YAML(typ="safe").load(
        (root / ".haru" / "litellm_server.yaml").read_text(encoding="utf-8")
    )
    deployment = config["model_list"][0]
    assert deployment["model_name"] == "haru:canonical"
    assert deployment["litellm_params"]["model"] == expected
    if api_base:
        assert deployment["litellm_params"]["api_base"] == api_base
    callbacks = config["litellm_settings"]["callbacks"]
    assert ("litellm_post_fix.proxy_handler_instance" in callbacks) == (
        provider == LLMProvider.BEDROCK
    )


def test_writer_removes_stale_overlay(tmp_path, monkeypatch) -> None:
    root = _repo(tmp_path)
    stale = root / ".haru" / "compose-retired.yaml"
    stale.parent.mkdir()
    stale.write_text("services:\n  retired: {}\n", encoding="utf-8")
    monkeypatch.setattr(configuration, "STACK_FILES", {"reasoner": "docker-compose-reasoner.yaml"})
    monkeypatch.setattr(
        configuration,
        "compatibility_payload",
        lambda _: {"schema_version": "3", "repo_revision": "test", "service_inventory": []},
    )
    ConfigurationWriter(root).write(SetupAnswers(deployment=Deployment.SIMULATOR))
    assert not stale.exists()


def test_compatibility_rejects_changed_checkout(tmp_path, monkeypatch) -> None:
    root = tmp_path
    local = root / ".haru"
    local.mkdir()
    stored = {
        "schema_version": "3",
        "repo_revision": "old",
        "service_inventory": ["all:service"],
    }
    (local / "compatibility.json").write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setattr(
        configuration,
        "compatibility_payload",
        lambda _: {
            "schema_version": "3",
            "repo_revision": "new",
            "service_inventory": ["all:service"],
        },
    )
    with pytest.raises(RuntimeError, match="does not match"):
        validate_compatibility(root)


@pytest.mark.parametrize(
    ("deployment", "gpu_enabled"),
    [
        (Deployment.PHYSICAL, False),
        (Deployment.PHYSICAL, True),
        (Deployment.SIMULATOR, False),
        (Deployment.SIMULATOR, True),
    ],
)
def test_generated_all_overlay_renders_for_deployment_matrix(
    tmp_path, monkeypatch, deployment, gpu_enabled
) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose is required")
    source_root = Path(__file__).resolve().parents[2]
    for directory in ("apps", "config", "envs"):
        shutil.copytree(source_root / directory, tmp_path / directory)
    monkeypatch.setattr(
        configuration,
        "compatibility_payload",
        lambda _: {
            "schema_version": "3",
            "repo_revision": "test",
            "service_inventory": [],
        },
    )
    answers = SetupAnswers(
        deployment=deployment,
        robot_host="haru-19.local" if deployment == Deployment.PHYSICAL else None,
        gpu_available=gpu_enabled,
    )
    ConfigurationWriter(tmp_path).write(answers)
    profiles = [
        "all",
        "gpu" if gpu_enabled else "cpu",
        deployment.value,
    ]
    environment = os.environ.copy()
    environment["COMPOSE_PROFILES"] = ",".join(profiles)
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(tmp_path / "apps" / "docker-compose-all.yaml"),
            "--env-file",
            str(tmp_path / "envs" / "all.env"),
            "--env-file",
            str(tmp_path / ".haru" / "local.env"),
            "-f",
            str(tmp_path / ".haru" / "compose-all.yaml"),
            "config",
            "--services",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    services = set(result.stdout.splitlines())
    assert ("haru-nlp-server-gpu" in services) == gpu_enabled
    assert ("haru-nlp-server-cpu" in services) != gpu_enabled
    assert ("unity-app" in services) == (deployment == Deployment.SIMULATOR)
    assert ("azure-kinect" in services) == (deployment == Deployment.PHYSICAL)
