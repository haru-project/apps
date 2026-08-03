#!/usr/bin/env python3
"""Validate the tracked perception deployment contract without starting it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any, Mapping


FACE_ENVIRONMENT = {
    "FACES_DATA_ROOT": "/ros/strawberry_ros_faces_module",
}

FACE_ALLOWED_ENVIRONMENT_KEYS = frozenset(
    set(FACE_ENVIRONMENT)
    | {
        "FACES_DEV_AUTOSTART",
        "FACES_USE_SIM_TIME",
        "FACES_USE_FFMPEG_DECODE_BRIDGE",
        "FACES_NAMESPACE",
        "FACES_RGB_TOPIC",
        "FACES_CAMERA_INFO_TOPIC",
    }
)

# Skeleton policy lives in the package defaults. Compose supplies only the
# deployment context needed to connect the image to this stack.
SKELETON_ENVIRONMENT: dict[str, str] = {}
SKELETON_ALLOWED_ENVIRONMENT_KEYS = frozenset(
    {
        "SKELETONS_DEV_AUTOSTART",
        "SKELETONS_USE_SIM_TIME",
        "SKELETONS_USE_FFMPEG_DECODE_BRIDGE",
        "SKELETONS_USE_ZDEPTH_DECODE_BRIDGE",
        "SKELETONS_RGB_TOPIC",
        "SKELETONS_RGB_FALLBACK_TOPIC",
        "SKELETONS_DEPTH_TOPIC",
        "SKELETONS_DEPTH_FALLBACK_TOPIC",
        "SKELETONS_CAMERA_INFO_TOPIC",
        "SKELETONS_OUTPUT_TOPIC_SKELETONS",
        "SKELETONS_FACES_TOPIC",
    }
)

SKELETON_PREFIXED_TOPIC_SUFFIXES = {
    "SKELETONS_RGB_FALLBACK_TOPIC": "/perception/proc/rgb/image_raw_ffmpeg_decoded",
    "SKELETONS_DEPTH_FALLBACK_TOPIC": (
        "/perception/proc/depth_to_rgb/image_raw_zdepth_decoded"
    ),
    "SKELETONS_FACES_TOPIC": "/perception/proc/faces",
}

SERVICE_IMAGE_REPOSITORIES = {
    "azure-kinect": "ghcr.io/haru-project/strawberry-ros-azure-kinect",
    "skeletons": "ghcr.io/haru-project/strawberry-ros-skeletons",
    "faces": "ghcr.io/haru-project/strawberry-ros-faces-module",
    "belief": "ghcr.io/haru-project/haru-belief",
    "viz": "ghcr.io/haru-project/haru-viz",
}
PERCEPTION_IMAGE_SERVICES = tuple(SERVICE_IMAGE_REPOSITORIES)

DATA_TARGETS = {
    "faces": "/ros/strawberry_ros_faces_module",
    "belief": "/ros/haru_perception_data",
}

PLAYBACK_TARGET = "/ros/haru_playback_registries"
VIZ_APP_TREE_TARGET = PurePosixPath("/workspace/haru-viz")
PULL_POLICY = "always"

LEGACY_STATE_MARKERS = (
    "gallery/face_gallery.npz",
    "config/face_recognition_runtime.json",
    "face_labels.json",
    "haru_belief/identity_registry.yaml",
)


def _is_within(path: Path, root: Path) -> bool:
    resolved_path = path.expanduser().resolve(strict=False)
    resolved_root = root.expanduser().resolve(strict=False)
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _volume_for_target(
    service: Mapping[str, Any], target: str
) -> Mapping[str, Any] | None:
    volumes = service.get("volumes", [])
    if not isinstance(volumes, list):
        return None
    for volume in volumes:
        if isinstance(volume, Mapping) and volume.get("target") == target:
            return volume
    return None


def _valid_ci_image(image: Any, repository: str) -> bool:
    if not isinstance(image, str):
        return False
    return (
        image == repository
        or image.startswith(f"{repository}:")
        or image.startswith(f"{repository}@")
    )


def _is_within_container_path(path: str, root: PurePosixPath) -> bool:
    candidate = PurePosixPath(path)
    return candidate == root or root in candidate.parents


def _unexpected_prefixed_keys(
    environment: Mapping[str, Any], prefix: str, allowed: frozenset[str]
) -> tuple[str, ...]:
    return tuple(
        sorted(
            key
            for key in environment
            if isinstance(key, str) and key.startswith(prefix) and key not in allowed
        )
    )


def _direct_parameter_override_keys(
    environment: Mapping[str, Any],
) -> tuple[str, ...]:
    """Find generic haru-launch overrides that bypass package-owned policy."""

    return tuple(
        sorted(
            key
            for key in environment
            if isinstance(key, str)
            and (key.startswith("HARU_PARAM__") or key.startswith("HARU_PARAM_MAP__"))
        )
    )


def _validate_host_bind(
    *,
    stack: str,
    service_name: str,
    volume: Mapping[str, Any] | None,
    target: str,
    repo_root: Path,
    errors: list[str],
    allow_legacy_root: bool = False,
) -> str | None:
    label = f"[{stack}] {service_name} mount {target}"
    if volume is None:
        errors.append(f"{label} is missing")
        return None
    if volume.get("type") != "bind":
        errors.append(f"{label} must be a bind mount")
    source = volume.get("source")
    if not isinstance(source, str) or not source:
        errors.append(f"{label} has no host source")
        return None
    source_path = Path(source).expanduser()
    if not source_path.is_absolute():
        errors.append(f"{label} source must be absolute, got {source!r}")
    elif _is_within(source_path, repo_root) and not (
        allow_legacy_root
        and source_path.expanduser().resolve(strict=False)
        == (repo_root / "data" / "perception").resolve(strict=False)
    ):
        errors.append(f"{label} source must be outside the repository, got {source!r}")
    bind = volume.get("bind")
    if not isinstance(bind, Mapping) or bind.get("create_host_path") is not False:
        errors.append(f"{label} must set bind.create_host_path=false")
    return str(source_path.resolve(strict=False))


def validate_rendered_configs(
    configs: Mapping[str, Mapping[str, Any]], repo_root: Path
) -> list[str]:
    """Return contract violations found in rendered Compose JSON."""

    errors: list[str] = []
    signatures: dict[str, tuple[Any, ...]] = {}

    for stack in ("perception", "all"):
        config = configs.get(stack)
        if not isinstance(config, Mapping):
            errors.append(f"[{stack}] rendered config is missing")
            continue
        services = config.get("services")
        if not isinstance(services, Mapping):
            errors.append(f"[{stack}] rendered services are missing")
            continue

        selected: dict[str, Mapping[str, Any]] = {}
        for service_name in PERCEPTION_IMAGE_SERVICES:
            service = services.get(service_name)
            if not isinstance(service, Mapping):
                errors.append(f"[{stack}] service {service_name} is missing")
                continue
            selected[service_name] = service
            repository = SERVICE_IMAGE_REPOSITORIES[service_name]
            image = service.get("image")
            if not _valid_ci_image(image, repository):
                errors.append(
                    f"[{stack}] {service_name} image must come from {repository}, "
                    f"got {image!r}"
                )
            pull_policy = service.get("pull_policy")
            if pull_policy != PULL_POLICY:
                errors.append(
                    f"[{stack}] {service_name} pull_policy must be "
                    f"{PULL_POLICY!r}, got {pull_policy!r}"
                )

        if len(selected) != len(PERCEPTION_IMAGE_SERVICES):
            continue

        face_environment = selected["faces"].get("environment", {})
        if not isinstance(face_environment, Mapping):
            errors.append(f"[{stack}] faces environment is missing")
            face_environment = {}
        for key, expected in FACE_ENVIRONMENT.items():
            actual = face_environment.get(key)
            if actual != expected:
                errors.append(
                    f"[{stack}] faces {key} must be {expected!r}, got {actual!r}"
                )
        unexpected_face_keys = _unexpected_prefixed_keys(
            face_environment, "FACES_", FACE_ALLOWED_ENVIRONMENT_KEYS
        )
        if unexpected_face_keys:
            errors.append(
                f"[{stack}] faces policy must come from the package; remove Compose "
                f"overrides {list(unexpected_face_keys)!r}"
            )
        direct_face_overrides = _direct_parameter_override_keys(face_environment)
        if direct_face_overrides:
            errors.append(
                f"[{stack}] faces policy must come from the package; remove direct "
                f"launch overrides {list(direct_face_overrides)!r}"
            )

        skeleton_service = selected.get("skeletons")
        skeleton_environment: Mapping[str, Any] = {}
        if not isinstance(skeleton_service, Mapping):
            errors.append(f"[{stack}] service skeletons is missing")
        else:
            raw_skeleton_environment = skeleton_service.get("environment", {})
            skeleton_environment = raw_skeleton_environment
            if not isinstance(skeleton_environment, Mapping):
                errors.append(f"[{stack}] skeletons environment is missing")
                skeleton_environment = {}
            for key, expected in SKELETON_ENVIRONMENT.items():
                actual = skeleton_environment.get(key)
                if actual != expected:
                    errors.append(
                        f"[{stack}] skeletons {key} must be {expected!r}, "
                        f"got {actual!r}"
                    )
            unexpected_skeleton_keys = _unexpected_prefixed_keys(
                skeleton_environment,
                "SKELETONS_",
                SKELETON_ALLOWED_ENVIRONMENT_KEYS,
            )
            if unexpected_skeleton_keys:
                errors.append(
                    f"[{stack}] skeleton policy must come from the package; remove "
                    f"Compose overrides {list(unexpected_skeleton_keys)!r}"
                )
            direct_skeleton_overrides = _direct_parameter_override_keys(
                skeleton_environment
            )
            if direct_skeleton_overrides:
                errors.append(
                    f"[{stack}] skeleton policy must come from the package; remove "
                    f"direct launch overrides {list(direct_skeleton_overrides)!r}"
                )
            topic_prefix = str(face_environment.get("HARU_TOPIC_PREFIX", "") or "")
            if topic_prefix and (
                not topic_prefix.startswith("/") or topic_prefix.endswith("/")
            ):
                errors.append(
                    f"[{stack}] HARU_TOPIC_PREFIX must be empty or an absolute "
                    f"prefix without a trailing slash, got {topic_prefix!r}"
                )
            skeleton_prefix = str(
                skeleton_environment.get("HARU_TOPIC_PREFIX", "") or ""
            )
            if skeleton_prefix != topic_prefix:
                errors.append(
                    f"[{stack}] skeleton HARU_TOPIC_PREFIX must match faces prefix "
                    f"{topic_prefix!r}, got {skeleton_prefix!r}"
                )
            for key, suffix in SKELETON_PREFIXED_TOPIC_SUFFIXES.items():
                expected = f"{topic_prefix}{suffix}"
                actual = skeleton_environment.get(key)
                if actual != expected:
                    errors.append(
                        f"[{stack}] skeletons {key} must follow HARU_TOPIC_PREFIX: "
                        f"expected {expected!r}, got {actual!r}"
                    )

        belief_environment = selected["belief"].get("environment", {})
        if not isinstance(belief_environment, Mapping):
            errors.append(f"[{stack}] belief environment is missing")
            belief_environment = {}
        if belief_environment.get("ROS_HOME") != DATA_TARGETS["belief"]:
            errors.append(
                f"[{stack}] belief ROS_HOME must be {DATA_TARGETS['belief']!r}, "
                f"got {belief_environment.get('ROS_HOME')!r}"
            )

        data_sources: dict[str, str | None] = {}
        for service_name, target in DATA_TARGETS.items():
            volume = _volume_for_target(selected[service_name], target)
            data_sources[service_name] = _validate_host_bind(
                stack=stack,
                service_name=service_name,
                volume=volume,
                target=target,
                repo_root=repo_root,
                errors=errors,
                allow_legacy_root=True,
            )
        if (
            data_sources["faces"] is not None
            and data_sources["belief"] is not None
            and data_sources["faces"] != data_sources["belief"]
        ):
            errors.append(
                f"[{stack}] faces and belief must share one host data root, got "
                f"{data_sources['faces']!r} and {data_sources['belief']!r}"
            )

        playback_sources: dict[str, str | None] = {}
        for service_name in ("faces", "belief", "viz"):
            volume = _volume_for_target(selected[service_name], PLAYBACK_TARGET)
            playback_sources[service_name] = _validate_host_bind(
                stack=stack,
                service_name=service_name,
                volume=volume,
                target=PLAYBACK_TARGET,
                repo_root=repo_root,
                errors=errors,
            )
        distinct_playback_sources = {
            source for source in playback_sources.values() if source is not None
        }
        if len(distinct_playback_sources) > 1:
            errors.append(
                f"[{stack}] faces, belief, and viz must share one playback registry "
                f"root, got {sorted(distinct_playback_sources)!r}"
            )

        viz_environment = selected["viz"].get("environment", {})
        if not isinstance(viz_environment, Mapping):
            errors.append(f"[{stack}] viz environment is missing")
            viz_environment = {}
        for key in (
            "HARU_RECORDER_PLAYBACK_REGISTRY_ROOT",
            "HARU_PARAM__PLAYBACK_REGISTRY_ROOT",
        ):
            actual = viz_environment.get(key)
            if actual != PLAYBACK_TARGET:
                errors.append(
                    f"[{stack}] viz {key} must be {PLAYBACK_TARGET!r}, got {actual!r}"
                )
        if "HARU_VIZ_REPO_ROOT" in viz_environment:
            errors.append(
                f"[{stack}] viz must use the application installed in its CI image; "
                "remove HARU_VIZ_REPO_ROOT"
            )
        viz_working_dir = selected["viz"].get("working_dir")
        if viz_working_dir:
            errors.append(
                f"[{stack}] viz must use the CI image working directory; remove "
                f"working_dir {viz_working_dir!r}"
            )
        viz_volumes = selected["viz"].get("volumes", [])
        if isinstance(viz_volumes, list):
            for volume in viz_volumes:
                if not isinstance(volume, Mapping) or volume.get("type") != "bind":
                    continue
                target = volume.get("target")
                if isinstance(target, str) and _is_within_container_path(
                    target, VIZ_APP_TREE_TARGET
                ):
                    errors.append(
                        f"[{stack}] viz bind target {target!r} shadows the application "
                        "installed in the CI image"
                    )
        topic_prefix = face_environment.get("HARU_TOPIC_PREFIX", "")
        if viz_environment.get("VITE_ROS_TOPIC_PREFIX") != topic_prefix:
            errors.append(
                f"[{stack}] viz VITE_ROS_TOPIC_PREFIX must match HARU_TOPIC_PREFIX "
                f"{topic_prefix!r}, got "
                f"{viz_environment.get('VITE_ROS_TOPIC_PREFIX')!r}"
            )

        signatures[stack] = (
            tuple(selected[name].get("image") for name in PERCEPTION_IMAGE_SERVICES),
            tuple(
                selected[name].get("pull_policy") for name in PERCEPTION_IMAGE_SERVICES
            ),
            tuple(face_environment.get(key) for key in FACE_ENVIRONMENT),
            tuple(
                skeleton_environment.get(key)
                for key in SKELETON_PREFIXED_TOPIC_SUFFIXES
            ),
            data_sources["faces"],
            tuple(playback_sources[name] for name in ("faces", "belief", "viz")),
            tuple(
                viz_environment.get(key)
                for key in (
                    "HARU_RECORDER_PLAYBACK_REGISTRY_ROOT",
                    "HARU_PARAM__PLAYBACK_REGISTRY_ROOT",
                    "VITE_ROS_TOPIC_PREFIX",
                )
            ),
        )

    if set(signatures) == {"perception", "all"} and (
        signatures["perception"] != signatures["all"]
    ):
        errors.append(
            "[cross-stack] perception and all disagree on images, perception "
            "policy, or persistent roots"
        )
    return errors


def _present_state_markers(root: Path) -> tuple[str, ...]:
    return tuple(marker for marker in LEGACY_STATE_MARKERS if (root / marker).is_file())


def legacy_state_migration_warning(repo_root: Path, selected_root: Path) -> str | None:
    """Warn about a deliberate migration choice; never mutate either tree."""

    legacy_root = (repo_root / "data" / "perception").resolve(strict=False)
    selected_root = selected_root.expanduser().resolve(strict=False)
    if legacy_root == selected_root:
        return None
    legacy_markers = _present_state_markers(legacy_root)
    if not legacy_markers or _present_state_markers(selected_root):
        return None
    markers = ", ".join(legacy_markers)
    return (
        f"legacy perception state exists at {legacy_root} ({markers}), but the "
        f"selected root {selected_root} has no recognized state. No files were "
        "copied or modified. Before deployment, explicitly choose either "
        "(A) review and copy the legacy state into the selected global root, or "
        "(B) set HARU_PERCEPTION_DATA_ROOT to the absolute legacy root for both "
        "config validation and `up`."
    )


def render_stack(repo_root: Path, stack: str) -> Mapping[str, Any]:
    command = [
        "bash",
        str(repo_root / "scripts" / "compose.sh"),
        stack,
        "config",
        "--format",
        "json",
    ]
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"failed to render {stack}: {detail}")
    try:
        rendered = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to parse rendered {stack} JSON: {exc}") from exc
    if not isinstance(rendered, Mapping):
        raise RuntimeError(f"rendered {stack} config is not an object")
    return rendered


def _selected_data_root(config: Mapping[str, Any]) -> Path | None:
    services = config.get("services", {})
    if not isinstance(services, Mapping):
        return None
    faces = services.get("faces", {})
    if not isinstance(faces, Mapping):
        return None
    volume = _volume_for_target(faces, DATA_TARGETS["faces"])
    if volume is None or not isinstance(volume.get("source"), str):
        return None
    return Path(volume["source"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-legacy-state-check",
        action="store_true",
        help="validate rendered configuration without inspecting legacy state markers",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]

    try:
        configs = {
            stack: render_stack(repo_root, stack) for stack in ("perception", "all")
        }
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = validate_rendered_configs(configs, repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if not args.skip_legacy_state_check:
        selected_root = _selected_data_root(configs["perception"])
        if selected_root is not None:
            warning = legacy_state_migration_warning(repo_root, selected_root)
            if warning:
                print(f"WARNING: {warning}", file=sys.stderr)

    print("Perception deployment preflight passed for perception and all.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
