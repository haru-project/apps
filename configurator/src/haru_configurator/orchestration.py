"""Docker Compose lifecycle and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Iterable

import docker
from docker.errors import DockerException, NotFound

from .configuration import load_answers
from .models import Deployment, SetupAnswers


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
        self.ensure_registry_access()
        answers = load_answers(self.root)
        stacks = [
            "tts",
            "perception",
            "speech",
            "nlp",
            "llm",
            "memory",
            "reasoner",
        ]
        if answers.timeline_compatibility_enabled:
            stacks.append("timeline-player")
        if answers.deployment == Deployment.SIMULATOR:
            stacks.insert(0, "simulator")
        if answers.ipad_enabled:
            stacks.append("ipad")
        if answers.projector_enabled:
            stacks.append("projector")
        for stack in stacks:
            profiles = {
                "tts": ["--profile", "all"],
                "timeline-player": ["--profile", "timeline-compat"],
            }.get(stack, [])
            env = (
                {"HARU_NLP_SERVER_GPU_ENABLED": str(answers.gpu_available).lower()}
                if stack == "nlp"
                else None
            )
            self.compose(stack, *profiles, "pull", env=env)

    def up(self) -> None:
        self.ensure_registry_access()
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
        perception_services = ["azure-kinect", "skeletons", "faces", "belief", "viz"]
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
        nlp_variant = "gpu" if answers.gpu_available else "cpu"
        nlp_service = f"haru-nlp-server-{nlp_variant}"
        nlp_env = {"HARU_NLP_SERVER_GPU_ENABLED": str(answers.gpu_available).lower()}
        self.compose(
            "nlp",
            "up",
            "redis",
            nlp_service,
            "--force-recreate",
            "-d",
            env=nlp_env,
        )
        self._wait_healthy(
            "haru-nlp-redis-1",
            f"haru-nlp-{nlp_service}-1",
            timeout=180,
        )
        self.compose("llm", "up", "action-args", "--force-recreate", "-d")
        self._wait_healthy("haru-llm-server-1", "haru-llm-action-args-1", timeout=180)
        self.compose("memory", "up", "--force-recreate", "-d")
        self.compose("reasoner", "up", "reasoner", "context-manager", "--force-recreate", "-d")
        if answers.deployment == Deployment.PHYSICAL:
            self._wait_robot_endpoints(timeout=120)
        self._ensure_timeline_endpoint(answers)
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
            ("nlp", ["--profile", "cpu", "--profile", "gpu"]),
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

    def ensure_registry_access(self) -> None:
        self.command("bash", "scripts/ensure_ghcr_access.sh")

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
            "Reasoner": "haru-reasoner-reasoner-1",
            "Behavior trees": "haru-reasoner-bt-forest-1",
        }
        if answers and answers.timeline_compatibility_enabled:
            container_checks["Timeline compatibility"] = (
                "haru-timeline-player-timeline-player-1"
            )
        if answers and (answers.zoom_h8_enabled or answers.kinect_transcription_enabled):
            container_checks["Speech recognition"] = "haru-speech-recognition-1"
        if answers:
            nlp_variant = "gpu" if answers.gpu_available else "cpu"
            container_checks["Haru NLP"] = f"haru-nlp-haru-nlp-server-{nlp_variant}-1"
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
            tts_servers = self._action_server_count("/haru2/action_tts")
            checks.append(
                Check("Robot TTS action server", tts_servers == 1, f"servers={tts_servers}")
            )
            timeline_servers = self._action_server_count("/haru2/play_timeline")
            checks.append(
                Check(
                    "Timeline action server",
                    timeline_servers == 1,
                    f"servers={timeline_servers}",
                )
            )
        if self._container_exists("haru-llm-server-1"):
            output, code = self.exec_command_in_container(
                "haru-llm-server-1",
                (
                    "python -c \"import json,urllib.request; "
                    "data=json.load(urllib.request.urlopen("
                    "'http://127.0.0.1:4000/v1/models',timeout=3)); "
                    "assert any(item['id']=='haru:canonical' for item in data['data'])\""
                ),
            )
            checks.append(
                Check(
                    "Canonical LLM model",
                    code == 0,
                    output.strip() or "haru:canonical available",
                )
            )
        if self._container_exists("haru-speech-recognition-1"):
            output, code = self.exec_ros(
                "haru-speech-recognition-1",
                "ros2 topic info /perception/proc/speech/asr/result",
            )
            match = re.search(r"Publisher count:\s*(\d+)", output)
            publishers = int(match.group(1)) if match else 0
            checks.append(
                Check("ASR result publisher", code == 0 and publishers == 1, f"publishers={publishers}")
            )
        return checks

    def exec_command_in_container(
        self, container_name: str, command: str
    ) -> tuple[str, int]:
        container = self.client.containers.get(container_name)
        result = container.exec_run(["bash", "-lc", command])
        return result.output.decode(errors="replace"), result.exit_code

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

    def _action_server_count(self, action_name: str) -> int:
        output, code = self.exec_ros(
            "haru-tts-ros-node-1",
            f"ros2 action info {action_name}",
        )
        if code != 0:
            return 0
        match = re.search(r"Action servers:\s*(\d+)", output)
        return int(match.group(1)) if match else 0

    def _wait_exact_action_server(self, action_name: str, timeout: int) -> None:
        deadline = time.monotonic() + timeout
        count = 0
        while time.monotonic() < deadline:
            count = self._action_server_count(action_name)
            if count == 1:
                return
            if count > 1:
                raise RuntimeError(
                    f"{action_name} has duplicate action servers: {count}"
                )
            time.sleep(2)
        raise TimeoutError(f"{action_name} action server count is {count}; expected 1")

    def _ensure_timeline_endpoint(self, answers: SetupAnswers) -> None:
        count = self._action_server_count("/haru2/play_timeline")
        if count > 1:
            raise RuntimeError(
                f"/haru2/play_timeline has duplicate action servers: {count}"
            )
        if count == 0 and answers.timeline_compatibility_enabled:
            self.compose(
                "timeline-player",
                "--profile",
                "timeline-compat",
                "up",
                "timeline-player",
                "--force-recreate",
                "-d",
            )
            self._wait_healthy(
                "haru-timeline-player-timeline-player-1",
                timeout=120,
            )
        self._wait_exact_action_server("/haru2/play_timeline", timeout=120)


def data_is_present(root: Path) -> bool:
    return not missing_data_scripts(root)


def missing_data_scripts(root: Path) -> list[str]:
    expected: Iterable[tuple[Path, str]] = (
        (root / "data" / "speech" / "configs" / "haru_speech.yaml", "download_speech_data.sh"),
        (root / "data" / "llm" / "configs" / "haru_llm.yaml", "download_llm_data.sh"),
        (root / "data" / "reasoner" / "tasks", "download_reasoner_data.sh"),
        (root / "data" / "tts" / "configs" / "strawberry_tts.yaml", "download_tts_data.sh"),
    )
    return [script for path, script in expected if not path.exists()]
