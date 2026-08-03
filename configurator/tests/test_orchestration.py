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


def test_pull_checks_registry_access_before_compose(monkeypatch) -> None:
    answers = SimpleNamespace(
        deployment=Deployment.PHYSICAL,
        timeline_compatibility_enabled=False,
        ipad_enabled=False,
        projector_enabled=False,
        gpu_available=True,
    )
    monkeypatch.setattr("haru_configurator.orchestration.load_answers", lambda _: answers)
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.root = Path("/repo")
    events: list[str] = []
    monkeypatch.setattr(
        orchestrator,
        "ensure_registry_access",
        lambda: events.append("registry"),
    )
    monkeypatch.setattr(
        orchestrator,
        "compose",
        lambda *args, **kwargs: events.append(f"compose:{args[0]}"),
    )

    orchestrator.pull()

    assert events[0] == "registry"
    assert events[1:] == [
        "compose:tts",
        "compose:perception",
        "compose:speech",
        "compose:nlp",
        "compose:llm",
        "compose:memory",
        "compose:reasoner",
    ]
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


def test_up_checks_driver_timeline_before_behavior_trees(monkeypatch) -> None:
    answers = SimpleNamespace(
        deployment=Deployment.PHYSICAL,
        zoom_h8_enabled=False,
        kinect_transcription_enabled=False,
        gpu_available=True,
        ipad_enabled=False,
        projector_enabled=False,
        timeline_compatibility_enabled=False,
    )
    monkeypatch.setattr("haru_configurator.orchestration.load_answers", lambda _: answers)
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.root = Path("/repo")
    compose_calls: list[tuple[str, ...]] = []
    compose_environments: dict[tuple[str, ...], dict[str, str] | None] = {}
    timeline_checks: list[object] = []

    def record_compose(*args, **kwargs) -> None:
        compose_calls.append(args)
        compose_environments[args] = kwargs.get("env")

    monkeypatch.setattr(orchestrator, "compose", record_compose)
    monkeypatch.setattr(orchestrator, "ensure_registry_access", lambda: None)
    monkeypatch.setattr(orchestrator, "_wait_healthy", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "_wait_robot_endpoints", lambda timeout: None)
    monkeypatch.setattr(
        orchestrator,
        "_ensure_timeline_endpoint",
        lambda selected: timeline_checks.append(selected),
    )

    orchestrator.up()

    forest_start = compose_calls.index(
        ("reasoner", "up", "bt-forest", "--force-recreate", "-d")
    )
    assert not any(call[0] == "timeline-player" for call in compose_calls)
    assert (
        "perception",
        "up",
        "azure-kinect",
        "skeletons",
        "faces",
        "belief",
        "viz",
        "--force-recreate",
        "-d",
    ) in compose_calls
    assert (
        "llm",
        "up",
        "action-args",
        "--force-recreate",
        "-d",
    ) in compose_calls
    assert not any("dashboard" in call for call in compose_calls)
    assert forest_start > 0
    nlp_start = (
        "nlp",
        "up",
        "redis",
        "haru-nlp-server-gpu",
        "--force-recreate",
        "-d",
    )
    assert nlp_start in compose_calls
    assert compose_environments[nlp_start] == {"HARU_NLP_SERVER_GPU_ENABLED": "true"}
    assert timeline_checks == [answers]


def test_timeline_compatibility_starts_only_when_endpoint_missing(monkeypatch) -> None:
    answers = SimpleNamespace(timeline_compatibility_enabled=True)
    orchestrator = Orchestrator.__new__(Orchestrator)
    counts = iter([0, 1])
    compose_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(orchestrator, "_action_server_count", lambda _: next(counts))
    monkeypatch.setattr(
        orchestrator, "compose", lambda *args, **kwargs: compose_calls.append(args)
    )
    monkeypatch.setattr(orchestrator, "_wait_healthy", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        orchestrator,
        "_wait_exact_action_server",
        lambda action, timeout: orchestrator._action_server_count(action),
    )

    orchestrator._ensure_timeline_endpoint(answers)

    assert compose_calls == [
        (
            "timeline-player",
            "--profile",
            "timeline-compat",
            "up",
            "timeline-player",
            "--force-recreate",
            "-d",
        )
    ]


def test_duplicate_timeline_servers_are_rejected(monkeypatch) -> None:
    answers = SimpleNamespace(timeline_compatibility_enabled=False)
    orchestrator = Orchestrator.__new__(Orchestrator)
    monkeypatch.setattr(orchestrator, "_action_server_count", lambda _: 2)
    with pytest.raises(RuntimeError, match="duplicate"):
        orchestrator._ensure_timeline_endpoint(answers)
