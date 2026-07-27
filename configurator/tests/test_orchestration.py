from pathlib import Path
from types import SimpleNamespace

import pytest

from haru_configurator.orchestration import Orchestrator, missing_data_scripts
from haru_configurator.models import Deployment


def test_missing_downloads_are_selected_individually(tmp_path: Path) -> None:
    speech = tmp_path / "data" / "speech" / "configs" / "haru_speech.yaml"
    speech.parent.mkdir(parents=True)
    speech.write_text("ready", encoding="utf-8")

    scripts = missing_data_scripts(tmp_path)

    assert "download_speech_data.sh" not in scripts
    assert "download_llm_data.sh" in scripts
    assert "download_reasoner_data.sh" in scripts
    assert "download_tts_data.sh" in scripts


def test_wait_action_endpoint_waits_until_action_is_visible(monkeypatch) -> None:
    orchestrator = Orchestrator.__new__(Orchestrator)
    results = iter([("", 0), ("/haru2/play_timeline\n", 0)])
    monkeypatch.setattr(orchestrator, "exec_ros", lambda *_: next(results))
    monkeypatch.setattr("haru_configurator.orchestration.time.sleep", lambda _: None)

    orchestrator._wait_action_endpoint("reasoner", "/haru2/play_timeline", timeout=1)


def test_wait_action_endpoint_times_out(monkeypatch) -> None:
    orchestrator = Orchestrator.__new__(Orchestrator)
    monkeypatch.setattr(orchestrator, "exec_ros", lambda *_: ("", 0))
    times = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr("haru_configurator.orchestration.time.monotonic", lambda: next(times))
    monkeypatch.setattr("haru_configurator.orchestration.time.sleep", lambda _: None)

    with pytest.raises(TimeoutError, match="/haru2/play_timeline"):
        orchestrator._wait_action_endpoint("reasoner", "/haru2/play_timeline", timeout=1)


def test_up_starts_and_checks_timeline_player_before_behavior_trees(monkeypatch) -> None:
    answers = SimpleNamespace(
        deployment=Deployment.PHYSICAL,
        kinect_enabled=False,
        zoom_h8_enabled=False,
        kinect_transcription_enabled=False,
        ipad_enabled=False,
        projector_enabled=False,
    )
    monkeypatch.setattr("haru_configurator.orchestration.load_answers", lambda _: answers)
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.root = Path("/repo")
    compose_calls: list[tuple[str, ...]] = []
    action_waits: list[tuple[str, str, int]] = []
    monkeypatch.setattr(orchestrator, "compose", lambda *args: compose_calls.append(args))
    monkeypatch.setattr(orchestrator, "_wait_healthy", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "_wait_robot_endpoints", lambda timeout: None)
    monkeypatch.setattr(
        orchestrator,
        "_wait_action_endpoint",
        lambda container, action, timeout: action_waits.append((container, action, timeout)),
    )

    orchestrator.up()

    timeline_start = compose_calls.index(
        ("timeline-player", "up", "timeline-player", "--force-recreate", "-d")
    )
    forest_start = compose_calls.index(
        ("reasoner", "up", "bt-forest", "--force-recreate", "-d")
    )
    assert timeline_start < forest_start
    assert action_waits == [
        ("haru-reasoner-reasoner-1", "/haru2/play_timeline", 120)
    ]
