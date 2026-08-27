from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRAWBERRY_TTS_IMAGE = (
    "ghcr.io/haru-project/strawberry-tts:hotfix-demo-issues@"
    "sha256:b821969db29250c0b3cb8ed5800d89222c1ee24cdec70591cc3380d406301daa"
)
REASONER_IMAGE = (
    "ghcr.io/haru-project/haru-agent-reasoner:feature-dynamic_group_gaze"
)
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
def test_strawberry_services_use_validated_hotfix_digest(service: str) -> None:
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
def test_reasoner_services_use_dynamic_group_gaze_image(service: str) -> None:
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
