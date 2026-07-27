"""Docker Compose lifecycle and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import time
from typing import Iterable

import docker
from docker.errors import DockerException, NotFound

from .configuration import load_answers
from .models import Deployment


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    details: str


class Orchestrator:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.client = docker.from_env()

    def command(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            list(args),
            cwd=self.root,
            env=merged_env,
            check=check,
            text=True,
            capture_output=capture,
        )

    def compose(self, stack: str, *args: str, **kwargs) -> subprocess.CompletedProcess[str]:
        return self.command("bash", "scripts/compose.sh", stack, *args, **kwargs)

    def pull(self) -> None:
        answers = load_answers(self.root)
        stacks = ["tts", "timeline-player", "perception", "speech", "llm", "memory", "reasoner"]
        if answers.deployment == Deployment.SIMULATOR:
            stacks.insert(0, "simulator")
        if answers.ipad_enabled:
            stacks.append("ipad")
        if answers.projector_enabled:
            stacks.append("projector")
        for stack in stacks:
            profiles = ["--profile", "all"] if stack == "tts" else []
            self.compose(stack, *profiles, "pull")

    def up(self) -> None:
        answers = load_answers(self.root)
        if answers.deployment == Deployment.SIMULATOR:
            self.compose("simulator", "up", "unity-app", "web-server", "--force-recreate", "-d")
        self.compose(
            "tts",
            "--profile",
            "tts",
            "--profile",
            "ros",
            "up",
            "gpt-sovits",
            "cerevoice-api",
            "tts-client",
            "ros-node",
            "--force-recreate",
            "-d",
        )
        self._wait_healthy("haru-tts-tts-client-1", "haru-tts-ros-node-1", timeout=180)
        self.compose("timeline-player", "up", "timeline-player", "--force-recreate", "-d")
        self._wait_healthy("haru-timeline-player-timeline-player-1", timeout=120)
        perception_services = ["belief", "viz"]
        if answers.kinect_enabled:
            perception_services[0:0] = ["azure-kinect", "skeletons", "faces"]
        self.compose("perception", "up", *perception_services, "--force-recreate", "-d")
        if answers.zoom_h8_enabled or answers.kinect_transcription_enabled:
            self.compose(
                "speech",
                "up",
                "audio",
                "recognition",
                "localization",
                "--force-recreate",
                "-d",
            )
        self.compose("llm", "up", "action-args", "dashboard", "--force-recreate", "-d")
        self._wait_healthy("haru-llm-server-1", "haru-llm-action-args-1", timeout=180)
        self.compose("memory", "up", "--force-recreate", "-d")
        self.compose("reasoner", "up", "reasoner", "context-manager", "--force-recreate", "-d")
        if answers.deployment == Deployment.PHYSICAL:
            self._wait_robot_endpoints(timeout=120)
        self._wait_action_endpoint(
            "haru-reasoner-reasoner-1",
            "/haru2/play_timeline",
            timeout=120,
        )
        self.compose("reasoner", "up", "bt-forest", "--force-recreate", "-d")
        self._wait_healthy(
            "haru-reasoner-reasoner-1",
            "haru-reasoner-context-manager-1",
            "haru-reasoner-bt-forest-1",
            timeout=120,
        )
        if answers.ipad_enabled:
            self.compose("ipad", "up", "--force-recreate", "-d")
        if answers.projector_enabled:
            self.compose("projector", "up", "--force-recreate", "-d")

    def down(self) -> None:
        for stack, profiles in (
            ("reasoner", []),
            ("timeline-player", []),
            ("memory", []),
            ("llm", []),
            ("speech", []),
            ("perception", []),
            ("tts", ["--profile", "all"]),
            ("simulator", []),
            ("ipad", []),
            ("projector", []),
            ("nlp", ["--profile", "all"]),
            ("domain-bridge", []),
        ):
            self.compose(stack, *profiles, "down", check=False)

    def clean_docker(self) -> None:
        self.command("docker", "system", "prune", "-f")

    def refresh_data(self) -> None:
        self.command("bash", "scripts/download_all_data.sh")

    def download_missing_data(self) -> None:
        for script in missing_data_scripts(self.root):
            self.command("bash", str(self.root / "scripts" / script))

    def validate(self) -> None:
        self.command("bash", "scripts/validate_compose.sh")

    def checks(self) -> list[Check]:
        checks: list[Check] = []
        try:
            info = self.client.info()
            checks.append(Check("Docker", True, info.get("ServerVersion", "available")))
        except DockerException as error:
            return [Check("Docker", False, str(error))]

        answers_path = self.root / ".haru" / "answers.yaml"
        checks.append(Check("Local configuration", answers_path.exists(), str(answers_path)))
        answers = load_answers(self.root) if answers_path.exists() else None
        result = self.command("bash", "scripts/validate_compose.sh", check=False, capture=True)
        checks.append(Check("Compose rendering", result.returncode == 0, result.stderr.strip() or "valid"))

        container_checks = {
            "LLM": "haru-llm-action-args-1",
            "TTS retrieval bridge": "haru-tts-ros-node-1",
            "Timeline player": "haru-timeline-player-timeline-player-1",
            "Reasoner": "haru-reasoner-reasoner-1",
            "Behavior trees": "haru-reasoner-bt-forest-1",
        }
        if answers and (answers.zoom_h8_enabled or answers.kinect_transcription_enabled):
            container_checks["Speech recognition"] = "haru-speech-recognition-1"
        for label, name in container_checks.items():
            try:
                container = self.client.containers.get(name)
                container.reload()
                status = container.attrs["State"].get("Health", {}).get("Status", container.status)
                checks.append(Check(label, status in {"healthy", "running"}, status))
            except NotFound:
                checks.append(Check(label, False, "not running"))

        if self._container_exists("haru-tts-ros-node-1"):
            output, code = self.exec_ros(
                "haru-tts-ros-node-1",
                "ros2 service list | grep -qx /strawberry/retrieve_tts_generation",
            )
            checks.append(Check("Expressive TTS retrieval", code == 0, output.strip() or "available"))
            output, code = self.exec_ros(
                "haru-tts-ros-node-1",
                "ros2 action info /haru2/action_tts",
            )
            server_count = output.count("/haru2_core_tts_subscriber_node")
            checks.append(Check("Robot TTS action server", code == 0 and server_count == 1, f"servers={server_count}"))
            output, code = self.exec_ros(
                "haru-tts-ros-node-1",
                "ros2 action list | grep -qx /haru2/play_timeline",
            )
            checks.append(Check("Timeline action", code == 0, output.strip() or "available"))
        return checks

    def exec_ros(self, container_name: str, command: str) -> tuple[str, int]:
        container = self.client.containers.get(container_name)
        shell = (
            "source /opt/ros/jazzy/setup.bash 2>/dev/null || true; "
            "source /ros2_ws/install/setup.bash 2>/dev/null || "
            "source /opt/ros/jazzy/workspace/install/setup.bash 2>/dev/null || true; "
            + command
        )
        result = container.exec_run(["bash", "-lc", shell])
        return result.output.decode(errors="replace"), result.exit_code

    def _wait_healthy(self, *container_names: str, timeout: int) -> None:
        deadline = time.monotonic() + timeout
        pending = set(container_names)
        while pending and time.monotonic() < deadline:
            for name in list(pending):
                try:
                    container = self.client.containers.get(name)
                    container.reload()
                except NotFound:
                    continue
                state = container.attrs["State"]
                health = state.get("Health", {}).get("Status")
                if health == "healthy" or (health is None and state.get("Running")):
                    pending.remove(name)
                elif health == "unhealthy" or state.get("Status") in {"exited", "dead"}:
                    raise RuntimeError(f"{name} failed during startup: {health or state.get('Status')}")
            time.sleep(2)
        if pending:
            raise TimeoutError(f"Timed out waiting for: {', '.join(sorted(pending))}")

    def _container_exists(self, name: str) -> bool:
        try:
            self.client.containers.get(name)
        except NotFound:
            return False
        return True

    def _wait_robot_endpoints(self, timeout: int) -> None:
        required_actions = ("/haru2/action_tts", "/haru2/action_custom_tts", "/haru2/look_at")
        deadline = time.monotonic() + timeout
        missing = list(required_actions)
        while time.monotonic() < deadline:
            output, code = self.exec_ros("haru-tts-ros-node-1", "ros2 action list")
            if code == 0:
                available = set(output.splitlines())
                missing = [name for name in required_actions if name not in available]
                if not missing:
                    return
            time.sleep(2)
        raise TimeoutError(f"Robot action endpoints unavailable: {', '.join(missing)}")

    def _wait_action_endpoint(self, container_name: str, action_name: str, timeout: int) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            output, code = self.exec_ros(container_name, "ros2 action list")
            if code == 0 and action_name in set(output.splitlines()):
                return
            time.sleep(2)
        raise TimeoutError(f"ROS action endpoint unavailable: {action_name}")


def data_is_present(root: Path) -> bool:
    return not missing_data_scripts(root)


def missing_data_scripts(root: Path) -> list[str]:
    expected: Iterable[tuple[Path, str]] = (
        (root / "data" / "speech" / "configs" / "haru_speech.yaml", "download_speech_data.sh"),
        (root / "data" / "llm" / "configs" / "litellm_server.yaml", "download_llm_data.sh"),
        (root / "data" / "reasoner" / "tasks", "download_reasoner_data.sh"),
        (root / "data" / "tts" / "configs" / "strawberry_tts.yaml", "download_tts_data.sh"),
    )
    return [script for path, script in expected if not path.exists()]
