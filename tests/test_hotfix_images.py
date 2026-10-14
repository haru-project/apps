from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRAWBERRY_TTS_IMAGE = 'ghcr.io/haru-project/strawberry-tts@sha256:567ed9cdc7507073857add15d35d827fdc09a78908fc3ffd17e6d63f08a14591'
REASONER_IMAGE = 'ghcr.io/haru-project/haru-agent-reasoner@sha256:2028176a021dc3b5f527ef0a3adb4fda42e7333b1189d7b1e93a533900e34e4e'
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


def test_multilingual_images_are_pullable_refs_and_no_local_builds_remain():
    assert not (ROOT / 'docker/multilingual').exists()
    assert not (ROOT / 'scripts/build_multilingual.sh').exists()
    assert not (ROOT / 'envs/demo.env').exists()
    for language in ('es', 'uk'):
        command = ['bash', str(ROOT / 'scripts/compose.sh'), 'all', '--language', language,
                   '--profile', '*', 'config', '--format', 'json']
        services = json.loads(subprocess.check_output(command, text=True))['services']
        for name in ('recognition', 'tts-client', 'ros-node', 'action-args', 'reasoner', 'episode-builder'):
            assert services[name]['image'].startswith('ghcr.io/haru-project/')
            assert '@sha256:' in services[name]['image']
            assert 'build' not in services[name]
