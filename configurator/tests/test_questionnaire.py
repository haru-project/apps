from __future__ import annotations

from pathlib import Path
import subprocess

import questionary

from haru_configurator import cli


def test_questionnaire_prompt_layouts_construct() -> None:
    prompts = [
        questionary.select("Deployment target", choices=["Physical robot", "Simulator"]),
        questionary.confirm("Enable Zoom H8 speech input?", default=True),
        questionary.text("LiteLLM host port", default="4050"),
        questionary.password("BEDROCK_MANTLE_API_KEY"),
    ]

    assert all(callable(prompt.ask) for prompt in prompts)


def test_kinect_perception_is_not_optional() -> None:
    cli_source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "haru_configurator"
        / "cli.py"
    ).read_text(encoding="utf-8")

    assert "Enable Azure Kinect perception?" not in cli_source


def test_fixed_defaults_are_not_questionnaire_prompts() -> None:
    cli_source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "haru_configurator"
        / "cli.py"
    ).read_text(encoding="utf-8")

    assert "Enable Groot behavior-tree windows?" not in cli_source
    assert "Start the local timeline compatibility server" not in cli_source


def test_default_ports_are_only_prompted_when_occupied(monkeypatch) -> None:
    prompts: list[str] = []
    monkeypatch.setattr(cli, "port_available", lambda port: port != 5173)
    monkeypatch.setattr(
        cli.questionary,
        "text",
        lambda message, **kwargs: prompts.append(message) or object(),
    )
    monkeypatch.setattr(
        cli,
        "ask",
        lambda prompt: "5180",
    )

    assert cli.port_or_prompt("haru-viz host port", 5173) == 5180
    assert prompts == ["haru-viz host port (default 5173 already occupied)"]

    prompts.clear()
    assert cli.port_or_prompt("LiteLLM host port", 4050) == 4050
    assert prompts == []


def test_zoom_input_defaults_yes_and_kinect_transcription_defaults_no(
    monkeypatch,
) -> None:
    prompts: list[tuple[str, bool]] = []
    responses = iter((True, False))
    monkeypatch.setattr(
        cli.questionary,
        "confirm",
        lambda message, *, default: prompts.append((message, default)) or object(),
    )
    monkeypatch.setattr(cli, "ask", lambda _: next(responses))

    assert cli.speech_input_answers() == (True, False)
    assert prompts == [
        ("Enable Zoom H8 speech input?", True),
        ("Enable Kinect microphone transcription?", False),
    ]


def test_disabling_zoom_requires_selecting_an_alternative_input(
    monkeypatch,
) -> None:
    selections: list[str] = []
    responses = iter((False, "kinect"))
    monkeypatch.setattr(cli.questionary, "confirm", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        cli.questionary,
        "select",
        lambda message, **kwargs: selections.append(message) or object(),
    )
    monkeypatch.setattr(cli, "ask", lambda _: next(responses))

    assert cli.speech_input_answers() == (False, True)
    assert selections == ["Select the alternative speech input"]


def test_command_failure_returns_exit_code_without_raising(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "app",
        lambda: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, ["docker", "pull"])
        ),
    )

    assert cli.main() == 1
