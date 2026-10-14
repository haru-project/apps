from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRAWBERRY_TTS_IMAGE = "haru-tts:multilingual"
REASONER_IMAGE = "haru-reasoner:multilingual"
STRAWBERRY_TTS_API_IMAGE = (
    "ghcr.io/haru-project/strawberry-tts-api:v0.3.2-cu126"
)


def compose_image(
    compose_file: str,
    env_file: str,
    service: str,
    *,
    profile: str | None = None,
) -> str:
    command = [
        "docker",
        "compose",
        "-f",
        str(ROOT / compose_file),
        "--env-file",
        str(ROOT / env_file),
    ]
    if profile is not None:
        command.extend(("--profile", profile))
    command.extend(("config", "--format", "json", service))
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)["services"][service]["image"]


@pytest.mark.parametrize("service", ("tts-client", "ros-node", "cerevoice-api"))
def test_strawberry_services_use_multilingual_image(service: str) -> None:
    assert (
        compose_image(
            "apps/docker-compose-tts.yaml",
            "envs/tts.env",
            service,
            profile="all",
        )
        == STRAWBERRY_TTS_IMAGE
    )


@pytest.mark.parametrize(
    "service",
    ("bt-forest", "reasoner", "context-manager", "execute-task-scenario", "execute-task-test"),
)
def test_reasoner_services_use_multilingual_image(service: str) -> None:
    assert (
        compose_image(
            "apps/docker-compose-reasoner.yaml",
            "envs/reasoner.env",
            service,
            profile="*",
        )
        == REASONER_IMAGE
    )


def test_strawberry_api_stays_on_validated_v032_image() -> None:
    assert (
        compose_image(
            "apps/docker-compose-tts.yaml",
            "envs/tts.env",
            "gpt-sovits",
            profile="all",
        )
        == STRAWBERRY_TTS_API_IMAGE
    )


def test_multilingual_builds_keep_validated_runtime_bases():
    # The source pin in sources.env identifies the reviewed TTS Dockerfile.
    assert 'TTS_REVISION=d580991eb858238eeaceef4c42f015904a62bf44' in (ROOT / 'docker/multilingual/sources.env').read_text()
    assert 'sha256:22b6584e21cee4366614d30ab369b5e710cc720e0ce602a9ca69327d6bee3cc9' in (ROOT / 'docker/multilingual/reasoner.Dockerfile').read_text()
