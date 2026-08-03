from __future__ import annotations

import json
from pathlib import Path

from haru_configurator.scenario import ScenarioManager
from haru_configurator.configuration import load_state, save_state


def test_scenario_runtime_copy_gets_monotonic_task_id(tmp_path: Path) -> None:
    source = tmp_path / "data" / "reasoner" / "tasks" / "episodes" / "demo.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"task_id": 6, "actions": []}', encoding="utf-8")
    manager = ScenarioManager.__new__(ScenarioManager)
    manager.root = tmp_path

    first_path, first_id = manager.prepare(source)
    second_path, second_id = manager.prepare(source)

    assert first_path != second_path
    assert second_id > first_id > 6
    assert json.loads(second_path.read_text(encoding="utf-8"))["task_id"] == second_id


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str]] = []

    def exec_ros(self, container: str, command: str) -> tuple[str, int]:
        self.commands.append((container, command))
        if "cancel_goal" in command:
            return "return_code=0", 0
        if "track_status" in command:
            return "tracking: false", 0
        return "", 0


def test_stop_cancels_recorded_goal_and_disables_tracking(tmp_path: Path) -> None:
    save_state(
        tmp_path,
        {
            "scenario_status": "running",
            "scenario_goal_id": "00112233445566778899aabbccddeeff",
        },
    )
    manager = ScenarioManager.__new__(ScenarioManager)
    manager.root = tmp_path
    manager.orchestrator = _FakeOrchestrator()

    manager.stop()

    commands = "\n".join(command for _, command in manager.orchestrator.commands)
    assert "cancel_goal" in commands
    assert "/simple_gaze_controller/kill_tree" in commands
    assert "{command: 2}" in commands
    assert "track_status" in commands
    assert load_state(tmp_path)["scenario_status"] == "canceled"
