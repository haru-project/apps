from __future__ import annotations

from pathlib import Path
import stat

from ruamel.yaml import YAML

from haru_configurator import configuration
from haru_configurator.configuration import ConfigurationWriter, has_provider_secret
from haru_configurator.models import Deployment, LLMProvider, SetupAnswers


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "apps").mkdir()
    (tmp_path / "config" / "behavior_trees").mkdir(parents=True)
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
    answers = SetupAnswers(
        deployment=Deployment.PHYSICAL,
        robot_host="haru-19.local",
        llm_provider=LLMProvider.BEDROCK,
        llm_model_id="gemma-4-26b-bedrock-eu-central-1",
        kinect_transcription_enabled=False,
    )
    ConfigurationWriter(root).write(answers, "secret-value")

    local_env = (root / ".haru" / "local.env").read_text(encoding="utf-8")
    assert "ROS_DOMAIN_ID=19" in local_env
    assert "HARU_NLP_SERVER_GPU_ENABLED=true" in local_env
    assert "secret-value" not in local_env
    override = (root / ".haru" / "compose-reasoner.yaml").read_text(encoding="utf-8")
    assert "expressivity_controller.xml" not in override
    assert "simple_gaze_controller.xml" in override
    secret_path = root / "envs" / "llm.secrets.env"
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
    assert "BEDROCK_API_KEY=secret-value" in secret_path.read_text(encoding="utf-8")
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
    ConfigurationWriter(root).write(SetupAnswers(deployment=Deployment.SIMULATOR))
    override = (root / ".haru" / "compose-reasoner.yaml").read_text(encoding="utf-8")
    assert "expressivity_controller.xml" not in override
