"""Reliable scenario preparation, execution, cancellation, and log capture."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any

from docker.errors import NotFound

from .configuration import load_state, save_state
from .orchestration import Orchestrator


GOAL_PATTERN = re.compile(r"Goal accepted with ID:\s*([0-9a-fA-F]{32})")
SUCCESS_PATTERN = re.compile(r"Goal finished with status:\s*SUCCEEDED")
DEFAULT_SCENARIO = Path("data/reasoner/tasks/episodes/20260527.json")
MAX_LOG_BYTES = 5_000_000


class ScenarioManager:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.orchestrator = Orchestrator(self.root)

    def prepare(self, source: Path) -> tuple[Path, int]:
        source = source if source.is_absolute() else self.root / source
        if not source.exists():
            raise FileNotFoundError(source)
        tasks_root = self.root / "data" / "reasoner" / "tasks"
        try:
            source.relative_to(tasks_root)
        except ValueError as error:
            raise ValueError(f"Scenario must be under {tasks_root}") from error

        payload = json.loads(source.read_text(encoding="utf-8"))
        state = load_state(self.root)
        previous = int(state.get("last_task_id", 0))
        source_id = int(payload.get("task_id", 0))
        task_id = max(previous + 1, source_id + 1, int(time.time()) % 2_000_000_000)
        payload["task_id"] = task_id
        runtime_dir = tasks_root / ".runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        destination = runtime_dir / f"{source.stem}-{task_id}.json"
        destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        state.update({"last_task_id": task_id, "prepared_scenario": str(destination)})
        save_state(self.root, state)
        return destination, task_id

    def run(self, source: Path = DEFAULT_SCENARIO, continue_session: bool = False) -> bool:
        state = load_state(self.root)
        if state.get("scenario_status") in {"starting", "running"}:
            self.stop(quiet=True)
        runtime_path, task_id = self.prepare(source)
        if not continue_session:
            self._fresh_services()
        relative = runtime_path.relative_to(self.root / "data" / "reasoner" / "tasks")
        started = datetime.now(timezone.utc)
        state = load_state(self.root)
        state.update(
            {
                "scenario_status": "starting",
                "scenario_task_id": task_id,
                "scenario_started_at": started.isoformat(),
                "scenario_file": str(runtime_path),
                "scenario_goal_id": None,
            }
        )
        save_state(self.root, state)
        self.orchestrator.compose(
            "reasoner",
            "up",
            "execute-task-scenario",
            "--force-recreate",
            "-d",
            env={"TASK_SCENARIO_FILE": str(relative)},
        )
        container = self._wait_for_container("haru-reasoner-execute-task-scenario-1")
        succeeded = False
        try:
            for raw in container.logs(stream=True, follow=True, timestamps=True):
                line = raw.decode(errors="replace")
                print(line, end="", flush=True)
                match = GOAL_PATTERN.search(line)
                if match:
                    state = load_state(self.root)
                    state.update({"scenario_goal_id": match.group(1), "scenario_status": "running"})
                    save_state(self.root, state)
                if SUCCESS_PATTERN.search(line):
                    succeeded = True
        except KeyboardInterrupt:
            self.stop()
            raise
        finally:
            container.reload()
            succeeded = succeeded and container.attrs["State"].get("ExitCode") == 0
            state = load_state(self.root)
            state.update(
                {
                    "scenario_status": "succeeded" if succeeded else "failed",
                    "scenario_finished_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            save_state(self.root, state)
        return succeeded

    def stop(self, quiet: bool = False) -> None:
        state = load_state(self.root)
        goal_id = state.get("scenario_goal_id")
        status = state.get("scenario_status")
        if goal_id and status in {"starting", "running"}:
            self._cancel_goal(goal_id)
        elif not quiet and status not in {"starting", "running"}:
            print("No active scenario goal recorded.")
        if status in {"starting", "running"}:
            self._stop_gaze()
            state["scenario_status"] = "canceled"
            state["scenario_finished_at"] = datetime.now(timezone.utc).isoformat()
            save_state(self.root, state)

    def capture_logs(self) -> Path:
        state = load_state(self.root)
        start_text = state.get("scenario_started_at")
        if not start_text:
            raise RuntimeError("No recorded scenario window")
        end_text = state.get("scenario_finished_at") or datetime.now(timezone.utc).isoformat()
        start = datetime.fromisoformat(start_text)
        end = datetime.fromisoformat(end_text)
        task_id = state.get("scenario_task_id", "unknown")
        output_dir = self.root / ".haru" / "logs" / f"scenario-{task_id}"
        output_dir.mkdir(parents=True, exist_ok=True)
        names = (
            "haru-reasoner-execute-task-scenario-1",
            "haru-reasoner-reasoner-1",
            "haru-reasoner-context-manager-1",
            "haru-reasoner-bt-forest-1",
            "haru-llm-action-args-1",
            "haru-tts-ros-node-1",
            "haru-tts-tts-client-1",
            "haru-tts-gpt-sovits-1",
            "haru-speech-recognition-1",
        )
        for name in names:
            try:
                container = self.orchestrator.client.containers.get(name)
            except NotFound:
                continue
            data = container.logs(since=start, until=end, timestamps=True, stdout=True, stderr=True)
            (output_dir / f"{name}.log").write_bytes(data)
        manifest = {
            "task_id": task_id,
            "status": state.get("scenario_status"),
            "started_at": start_text,
            "finished_at": end_text,
            "scenario_file": state.get("scenario_file"),
            "goal_id": state.get("scenario_goal_id"),
            "max_bytes_per_container": MAX_LOG_BYTES,
            "truncated_logs": [],
        }
        truncated: list[str] = []
        for log_path in output_dir.glob("*.log"):
            size = log_path.stat().st_size
            if size > MAX_LOG_BYTES:
                log_path.write_bytes(log_path.read_bytes()[-MAX_LOG_BYTES:])
                truncated.append(log_path.name)
        manifest["truncated_logs"] = truncated
        (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return output_dir

    def _fresh_services(self) -> None:
        try:
            self.orchestrator.exec_ros(
                "haru-reasoner-context-manager-1",
                "rm -f /tmp/haru_agent_reasoner/context.backup",
            )
        except NotFound:
            pass
        self.orchestrator.compose(
            "llm", "up", "redis", "server", "action-args", "--force-recreate", "-d"
        )
        self.orchestrator.compose(
            "reasoner", "up", "reasoner", "context-manager", "--force-recreate", "-d"
        )
        self.orchestrator.compose("reasoner", "up", "bt-forest", "--force-recreate", "-d")
        self.orchestrator._wait_healthy(
            "haru-llm-action-args-1",
            "haru-reasoner-reasoner-1",
            "haru-reasoner-context-manager-1",
            "haru-reasoner-bt-forest-1",
            timeout=180,
        )

    def _cancel_goal(self, goal_id: str) -> None:
        uuid = [int(goal_id[index : index + 2], 16) for index in range(0, 32, 2)]
        request = "{goal_info: {goal_id: {uuid: [" + ", ".join(map(str, uuid)) + "]}}}"
        command = (
            "ros2 service call /haru_agent/new_task_raw/_action/cancel_goal "
            f"action_msgs/srv/CancelGoal \"{request}\""
        )
        for name in (
            "haru-reasoner-execute-task-scenario-1",
            "haru-reasoner-reasoner-1",
        ):
            try:
                output, code = self.orchestrator.exec_ros(name, command)
            except NotFound:
                continue
            if code == 0 and re.search(r"return_code\s*[:=]\s*0", output):
                return
        raise RuntimeError(f"Failed to cancel scenario goal {goal_id}")

    def _stop_gaze(self) -> None:
        try:
            self.orchestrator.exec_ros(
                "haru-reasoner-bt-forest-1",
                "timeout 8 ros2 service call /simple_gaze_controller/kill_tree std_srvs/srv/Empty '{}' || true",
            )
        except NotFound:
            pass
        try:
            output, code = self.orchestrator.exec_ros(
                "haru-tts-ros-node-1",
                (
                    "timeout 8 ros2 topic pub --once /haru2/cmd_track "
                    "haru2_core_msgs/msg/TrackCommand '{command: 2}' >/dev/null; "
                    "sleep 1; timeout 6 ros2 topic echo /haru2/track_status --once"
                ),
            )
            if code != 0 or not re.search(r"tracking\s*:\s*false", output, re.IGNORECASE):
                raise RuntimeError("Robot did not confirm tracking: false")
        except NotFound:
            pass

    def _wait_for_container(self, name: str, timeout: int = 30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                return self.orchestrator.client.containers.get(name)
            except NotFound:
                time.sleep(0.5)
        raise TimeoutError(f"Container {name} did not appear")
