"""Generate ignored host-local configuration without changing tracked defaults."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Any

from dotenv import dotenv_values
from ruamel.yaml import YAML

from .models import AGENT_MODEL_KEYS, Deployment, LLMProvider, SetupAnswers


STACK_FILES = {
    "domain-bridge": "docker-compose-domain-bridge.yaml",
    "perception": "docker-compose-perception.yaml",
    "speech": "docker-compose-speech.yaml",
    "llm": "docker-compose-llm.yaml",
    "reasoner": "docker-compose-reasoner.yaml",
    "tts": "docker-compose-tts.yaml",
    "simulator": "docker-compose-simulator.yaml",
    "ipad": "docker-compose-ipad.yaml",
    "projector": "docker-compose-projector.yaml",
    "user": "docker-compose-user.yaml",
    "nlp": "docker-compose-nlp.yaml",
    "timeline-player": "docker-compose-timeline-player.yaml",
    "memory": "docker-compose-memory.yaml",
    "all": "docker-compose-all.yaml",
}


class ConfigurationWriter:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.local_dir = self.root / ".haru"
        self.yaml = YAML()
        self.yaml.default_flow_style = False

    def write(self, answers: SetupAnswers, secret: str | None = None) -> None:
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self._remove_stale_overlays()
        self._write_answers(answers)
        self._write_local_env(answers)
        self._write_compose_overrides(answers)
        self._write_domain_bridge(answers)
        self._write_speech_config(answers)
        self._write_litellm(answers)
        if secret:
            self._write_secret(answers.secret_name, secret)
        elif answers.llm_provider == LLMProvider.BEDROCK:
            self._migrate_legacy_bedrock_secret()
        self._write_compatibility()

    def _remove_stale_overlays(self) -> None:
        expected = {f"compose-{stack}.yaml" for stack in STACK_FILES}
        for path in self.local_dir.glob("compose-*.yaml"):
            if path.name not in expected:
                path.unlink()

    def _write_answers(self, answers: SetupAnswers) -> None:
        path = self.local_dir / "answers.yaml"
        with path.open("w", encoding="utf-8") as stream:
            self.yaml.dump(answers.model_dump(mode="json"), stream)

    def _write_local_env(self, answers: SetupAnswers) -> None:
        values: dict[str, str] = {
            "ROS_DOMAIN_ID": str(answers.robot_domain_id),
            "HARU_ROBOT_ROS_DOMAIN_ID": str(answers.robot_domain_id),
            "HARU_PERCEPTION_ROS_DOMAIN_ID": str(answers.perception_domain_id),
            "FROM_DOMAIN_ID": str(answers.perception_domain_id),
            "TO_DOMAIN_ID": str(answers.robot_domain_id),
            "HARU_VIZ_UI_PORT": str(answers.viz_port),
            "HARU_ROSBRIDGE_PORT": str(answers.rosbridge_port),
            "HARU_ROSBRIDGE_RGB_PORT": str(answers.rosbridge_port + 1),
            "HARU_ROSBRIDGE_DEPTH_PORT": str(answers.rosbridge_port + 2),
            "HARU_ROSBRIDGE_DEPTH_TO_RGB_PORT": str(answers.rosbridge_port + 3),
            "LLM_SERVER_HOST_PORT": str(answers.llm_port),
            "LLM_SERVER_BASE_URL": f"http://127.0.0.1:{answers.llm_port}/v1",
            "BEDROCK_MANTLE_REGION": answers.bedrock_region,
            "GROOT_MONITOR_ENABLED": str(answers.groot_enabled).lower(),
            "HARU_DEPLOYMENT": answers.deployment.value,
            "HARU_ROBOT_HOST": answers.robot_host or "",
            "HARU_GPU_AVAILABLE": str(answers.gpu_available).lower(),
            "HARU_NLP_SERVER_GPU_ENABLED": str(answers.gpu_available).lower(),
            "HARU_NLP_SERVER_HOST_PORT": str(answers.nlp_port),
            "AGENT_MEMORY_WEAVIATE_HTTP_PORT": str(answers.memory_http_port),
            "AGENT_MEMORY_WEAVIATE_GRPC_PORT": str(answers.memory_grpc_port),
            "CEREVOICE_HOST_PORT": str(answers.cerevoice_port),
            "GPT_SOVITS_HOST_PORT": str(answers.gpt_sovits_port),
            "TTS_API_HOST_PORT": str(answers.tts_api_port),
            "SIMULATOR_WEB_HOST_PORT": str(answers.simulator_web_port),
            "PROJECTOR_HOST_PORT": str(answers.projector_port),
            "EPISODE_BUILDER_PORT": str(answers.episode_builder_port),
            "HARU_HOST_HOME": answers.host_home,
            "HARU_SPEECH_STATE_DIR": str(Path(answers.host_home) / ".ros" / "haru_speech"),
            "HARU_SPEECH_MODELS_HOST_DIR": str(
                Path(answers.host_home) / "haru-speech-cache" / "models"
            ),
            "HARU_SPEECH_VOICES_HOST_DIR": str(
                Path(answers.host_home) / "haru-speech-cache" / "voices"
            ),
            "HARU_SKELETON_MODELS_HOST_DIR": str(
                Path(answers.host_home) / "haru-perception-cache" / "skeletons" / "models"
            ),
            "HARU_HF_CACHE_HOST_DIR": str(Path(answers.host_home) / ".cache" / "huggingface"),
            "HARU_VIZ_HOST_RECORDINGS_DIR": str(
                Path(answers.host_home) / ".local" / "share" / "haru_viz" / "recordings"
            ),
            "PULSE_SOCKET_PATH": answers.pulse_socket_path,
            "UNITY_CONTROLLER_ENABLED": str(
                answers.deployment == Deployment.SIMULATOR
            ).lower(),
            "EXPRESSIVITY_CONTROLLER_ENABLED": "true",
            "GAZE_CONTROLLER_ENABLED": "true",
        }
        values.update({key: "haru:canonical" for key in AGENT_MODEL_KEYS})
        path = self.local_dir / "local.env"
        path.write_text(
            "# Generated by haru-local. Re-run setup instead of editing.\n"
            + "".join(f"{key}={value}\n" for key, value in values.items()),
            encoding="utf-8",
        )

    def _write_compose_overrides(self, answers: SetupAnswers) -> None:
        local_env = str(self.local_dir / "local.env")
        behavior_dir = self.root / "config" / "behavior_trees"
        for stack, filename in STACK_FILES.items():
            source = self.root / "apps" / filename
            if not source.exists():
                continue
            with source.open(encoding="utf-8") as stream:
                compose = self.yaml.load(stream) or {}
            services = compose.get("services", {})
            override: dict[str, Any] = {
                "services": {
                    name: {"env_file": [{"path": local_env, "required": True}]}
                    for name in services
                }
            }
            if stack in {"reasoner", "all"} and answers.deployment == Deployment.PHYSICAL:
                service_name = "bt-forest"
                if service_name in override["services"]:
                    override["services"][service_name]["volumes"] = [
                        (
                            f"{behavior_dir / 'simple_gaze_controller.xml'}:"
                            "/opt/ros/jazzy/workspace/install/share/behavior_tree_strawberry/"
                            "bt_palettes/simple_gaze_controller.xml:ro"
                        ),
                    ]
            path = self.local_dir / f"compose-{stack}.yaml"
            with path.open("w", encoding="utf-8") as stream:
                self.yaml.dump(override, stream)

    def _write_domain_bridge(self, answers: SetupAnswers) -> None:
        source = self.root / "config" / "domain_bridge.yaml"
        with source.open(encoding="utf-8") as stream:
            config = self.yaml.load(stream)
        config["from_domain"] = answers.perception_domain_id
        config["to_domain"] = answers.robot_domain_id
        destination = self.local_dir / "domain_bridge.yaml"
        with destination.open("w", encoding="utf-8") as stream:
            self.yaml.dump(config, stream)
        for stack in ("domain-bridge", "all"):
            path = self.local_dir / f"compose-{stack}.yaml"
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as stream:
                override = self.yaml.load(stream)
            service = override.get("services", {}).get("domain-bridge")
            if service is not None:
                service.setdefault("volumes", []).append(
                    f"{destination}:/shared/config/domain_bridge.yaml:ro"
                )
            with path.open("w", encoding="utf-8") as stream:
                self.yaml.dump(override, stream)

    def _write_speech_config(self, answers: SetupAnswers) -> None:
        source_path = self.root / "data" / "speech" / "configs" / "haru_speech.yaml"
        if not source_path.exists():
            return
        with source_path.open(encoding="utf-8") as stream:
            config = self.yaml.load(stream)
        parameters = config.get("/**/speech_stack", {}).get("ros__parameters", {})
        for source in parameters.get("sources", []):
            if source.get("source_id") == "mic_0":
                source["enabled"] = answers.zoom_h8_enabled
            elif source.get("source_id") == "mic_1":
                source["enabled"] = answers.kinect_enabled
                source["capture_enabled"] = answers.kinect_transcription_enabled
                source["speech_enabled"] = answers.kinect_transcription_enabled
        path = self.local_dir / "haru_speech.yaml"
        with path.open("w", encoding="utf-8") as stream:
            self.yaml.dump(config, stream)
        for stack in ("speech", "all"):
            override_path = self.local_dir / f"compose-{stack}.yaml"
            if not override_path.exists():
                continue
            with override_path.open(encoding="utf-8") as stream:
                override = self.yaml.load(stream)
            speech_services = {
                "base",
                "audio",
                "audio-capture-manager",
                "recognition",
                "verification",
                "localization",
            }
            for name, service in override.get("services", {}).items():
                if name not in speech_services:
                    continue
                service.setdefault("volumes", []).append(
                    f"{path}:/shared/configs/haru_speech.yaml:ro"
                )
            with override_path.open("w", encoding="utf-8") as stream:
                self.yaml.dump(override, stream)

    def _write_secret(self, name: str, value: str) -> None:
        path = self.root / "envs" / "llm.secrets.env"
        existing = (
            {key: stored_value or "" for key, stored_value in dotenv_values(path).items()}
            if path.exists()
            else {}
        )
        existing[name] = value
        template_keys = (
            "LLM_SERVER_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "HF_TOKEN",
            "BEDROCK_MANTLE_API_KEY",
            # Read only for one-time migration from pre-schema-3 setups.
            "BEDROCK_API_KEY",
            "CUSTOM_LLM_API_KEY",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
        )
        path.write_text("".join(f"{key}={existing.get(key, '')}\n" for key in template_keys), encoding="utf-8")
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def _write_litellm(self, answers: SetupAnswers) -> None:
        provider_prefix = {
            LLMProvider.BEDROCK: "bedrock_mantle",
            LLMProvider.OPENAI: "openai",
            LLMProvider.ANTHROPIC: "anthropic",
            LLMProvider.CUSTOM: "openai",
        }[answers.llm_provider]
        params: dict[str, Any] = {
            "model": f"{provider_prefix}/{answers.llm_model_id}",
            "api_key": f"os.environ/{answers.secret_name}",
        }
        if answers.llm_provider == LLMProvider.BEDROCK:
            params.update({"temperature": 1.0, "top_p": 0.95})
        if answers.llm_provider == LLMProvider.CUSTOM:
            if not answers.llm_api_base:
                raise ValueError("Custom provider requires llm_api_base")
            params["api_base"] = answers.llm_api_base
        callbacks = (
            ["litellm_post_fix.proxy_handler_instance"]
            if answers.llm_provider == LLMProvider.BEDROCK
            else []
        )
        config = {
            "model_list": [
                {
                    "model_name": "haru:canonical",
                    "litellm_params": params,
                }
            ],
            "litellm_settings": {
                "drop_params": True,
                "callbacks": callbacks,
            },
        }
        destination = self.local_dir / "litellm_server.yaml"
        with destination.open("w", encoding="utf-8") as stream:
            self.yaml.dump(config, stream)
        for stack in ("llm", "all"):
            path = self.local_dir / f"compose-{stack}.yaml"
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as stream:
                override = self.yaml.load(stream)
            server = override.get("services", {}).get("server")
            if server is not None:
                server.setdefault("volumes", []).append(f"{destination}:/app/config.yaml:ro")
            with path.open("w", encoding="utf-8") as stream:
                self.yaml.dump(override, stream)

    def _migrate_legacy_bedrock_secret(self) -> None:
        path = self.root / "envs" / "llm.secrets.env"
        if not path.exists():
            return
        existing = {
            key: stored_value or "" for key, stored_value in dotenv_values(path).items()
        }
        if not existing.get("BEDROCK_MANTLE_API_KEY") and existing.get("BEDROCK_API_KEY"):
            self._write_secret("BEDROCK_MANTLE_API_KEY", existing["BEDROCK_API_KEY"])

    def _write_compatibility(self) -> None:
        payload = compatibility_payload(self.root)
        path = self.local_dir / "compatibility.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def load_answers(root: Path) -> SetupAnswers:
    path = root / ".haru" / "answers.yaml"
    if not path.exists():
        raise FileNotFoundError("Run './setup.sh setup' first")
    yaml = YAML(typ="safe")
    with path.open(encoding="utf-8") as stream:
        answers = SetupAnswers.model_validate(yaml.load(stream))
    validate_compatibility(root)
    return answers


def has_provider_secret(root: Path, answers: SetupAnswers) -> bool:
    path = root / "envs" / "llm.secrets.env"
    if not path.exists():
        return False
    values = dotenv_values(path)
    if values.get(answers.secret_name):
        return True
    return bool(
        answers.llm_provider == LLMProvider.BEDROCK and values.get("BEDROCK_API_KEY")
    )


def service_inventory(root: Path) -> list[str]:
    yaml = YAML(typ="rt")
    inventory: list[str] = []
    for stack, filename in STACK_FILES.items():
        source = root / "apps" / filename
        if not source.exists():
            continue
        with source.open(encoding="utf-8") as stream:
            compose = yaml.load(stream) or {}
        inventory.extend(f"{stack}:{name}" for name in compose.get("services", {}))
    return sorted(inventory)


def compatibility_payload(root: Path) -> dict[str, Any]:
    revision = os.environ.get("HARU_REPO_REVISION")
    if not revision:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    schema_version = (
        root / "configurator" / "schema-version"
    ).read_text(encoding="utf-8").strip()
    return {
        "schema_version": schema_version,
        "repo_revision": revision,
        "service_inventory": service_inventory(root),
    }


def validate_compatibility(root: Path) -> None:
    path = root / ".haru" / "compatibility.json"
    if not path.exists():
        raise RuntimeError("Generated configuration is stale; run './setup.sh setup'")
    stored = json.loads(path.read_text(encoding="utf-8"))
    current = compatibility_payload(root)
    if stored != current:
        raise RuntimeError(
            "Generated configuration does not match this checkout; run './setup.sh setup'"
        )
    yaml = YAML(typ="rt")
    for stack, filename in STACK_FILES.items():
        overlay_path = root / ".haru" / f"compose-{stack}.yaml"
        source_path = root / "apps" / filename
        if not overlay_path.exists() or not source_path.exists():
            continue
        with source_path.open(encoding="utf-8") as stream:
            source_services = set((yaml.load(stream) or {}).get("services", {}))
        with overlay_path.open(encoding="utf-8") as stream:
            overlay_services = set((yaml.load(stream) or {}).get("services", {}))
        unknown = sorted(overlay_services - source_services)
        if unknown:
            raise RuntimeError(
                f"Generated {stack} overlay contains unknown services: {', '.join(unknown)}; "
                "run './setup.sh setup'"
            )


def load_state(root: Path) -> dict[str, Any]:
    path = root / ".haru" / "state.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / ".haru" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
