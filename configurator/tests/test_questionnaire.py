from __future__ import annotations

import questionary


def test_questionnaire_prompt_layouts_construct() -> None:
    prompts = [
        questionary.select("Deployment target", choices=["Physical robot", "Simulator"]),
        questionary.confirm("Enable Zoom H8 speech input?", default=True),
        questionary.text("LiteLLM host port", default="4050"),
        questionary.password("BEDROCK_MANTLE_API_KEY"),
    ]

    assert all(callable(prompt.ask) for prompt in prompts)
