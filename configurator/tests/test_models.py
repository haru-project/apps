from __future__ import annotations

import pytest
from pydantic import ValidationError

from haru_configurator.models import (
    Deployment,
    LLMProvider,
    PROVIDER_DEFAULTS,
    SetupAnswers,
)


def test_physical_robot_derives_domain() -> None:
    answers = SetupAnswers(
        deployment=Deployment.PHYSICAL,
        robot_host="haru-19.local",
        llm_provider=LLMProvider.BEDROCK,
    )
    assert answers.robot_id == 19
    assert answers.robot_domain_id == 19


def test_physical_robot_requires_canonical_hostname() -> None:
    with pytest.raises(ValidationError):
        SetupAnswers(deployment=Deployment.PHYSICAL, robot_host="robot.local")


def test_simulator_keeps_configured_domain() -> None:
    answers = SetupAnswers(deployment=Deployment.SIMULATOR, robot_domain_id=7)
    assert answers.robot_host is None
    assert answers.robot_domain_id == 7


@pytest.mark.parametrize(
    ("provider", "secret_name"),
    [
        (LLMProvider.BEDROCK, "BEDROCK_MANTLE_API_KEY"),
        (LLMProvider.OPENAI, "OPENAI_API_KEY"),
        (LLMProvider.ANTHROPIC, "ANTHROPIC_API_KEY"),
        (LLMProvider.CUSTOM, "CUSTOM_LLM_API_KEY"),
    ],
)
def test_provider_secret_mapping(provider: LLMProvider, secret_name: str) -> None:
    answers = SetupAnswers(deployment=Deployment.SIMULATOR, llm_provider=provider)
    assert answers.secret_name == secret_name
    assert PROVIDER_DEFAULTS[provider][0]


def test_host_ports_must_be_distinct() -> None:
    with pytest.raises(ValidationError):
        SetupAnswers(deployment=Deployment.SIMULATOR, llm_port=5173)


def test_host_paths_are_absolute(monkeypatch) -> None:
    with pytest.raises(ValidationError):
        SetupAnswers(deployment=Deployment.SIMULATOR, host_home="relative")
