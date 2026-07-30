from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_perception_deployment.py"
)
SPEC = importlib.util.spec_from_file_location(
    "check_perception_deployment", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def _bind(source: Path, target: str) -> dict[str, object]:
    return {
        "type": "bind",
        "source": str(source),
        "target": target,
        "bind": {"create_host_path": False},
    }


def _rendered_config(data_root: Path, playback_root: Path) -> dict[str, object]:
    return {
        "services": {
            "azure-kinect": {
                "image": "ghcr.io/haru-project/strawberry-ros-azure-kinect:tested",
                "pull_policy": preflight.PULL_POLICY,
            },
            "skeletons": {
                "image": ("ghcr.io/haru-project/strawberry-ros-skeletons:tested"),
                "pull_policy": preflight.PULL_POLICY,
                "environment": {
                    **preflight.SKELETON_ENVIRONMENT,
                    "HARU_TOPIC_PREFIX": "",
                    **{
                        key: suffix
                        for key, suffix in preflight.SKELETON_PREFIXED_TOPIC_SUFFIXES.items()
                    },
                },
            },
            "faces": {
                "image": ("ghcr.io/haru-project/strawberry-ros-faces-module:tested"),
                "pull_policy": preflight.PULL_POLICY,
                "environment": dict(preflight.FACE_ENVIRONMENT),
                "volumes": [
                    _bind(data_root, preflight.DATA_TARGETS["faces"]),
                    _bind(playback_root, preflight.PLAYBACK_TARGET),
                ],
            },
            "belief": {
                "image": "ghcr.io/haru-project/haru-belief@sha256:1234",
                "pull_policy": preflight.PULL_POLICY,
                "environment": {"ROS_HOME": preflight.DATA_TARGETS["belief"]},
                "volumes": [
                    _bind(data_root, preflight.DATA_TARGETS["belief"]),
                    _bind(playback_root, preflight.PLAYBACK_TARGET),
                ],
            },
            "viz": {
                "image": "ghcr.io/haru-project/haru-viz:tested",
                "pull_policy": preflight.PULL_POLICY,
                "environment": {
                    "HARU_RECORDER_PLAYBACK_REGISTRY_ROOT": preflight.PLAYBACK_TARGET,
                    "HARU_PARAM__PLAYBACK_REGISTRY_ROOT": preflight.PLAYBACK_TARGET,
                    "VITE_ROS_TOPIC_PREFIX": "",
                },
                "volumes": [_bind(playback_root, preflight.PLAYBACK_TARGET)],
            },
        }
    }


class PerceptionDeploymentPreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.base = Path(self.temporary_directory.name)
        self.repo_root = self.base / "repo"
        self.repo_root.mkdir()
        self.data_root = self.base / "global-data"
        self.playback_root = self.base / "global-playback"
        rendered = _rendered_config(self.data_root, self.playback_root)
        self.configs = {
            "perception": rendered,
            "all": copy.deepcopy(rendered),
        }

    def test_valid_config_passes(self) -> None:
        self.assertEqual(
            [], preflight.validate_rendered_configs(self.configs, self.repo_root)
        )

    def test_only_face_storage_is_explicit(self) -> None:
        expected = {
            "FACES_DATA_ROOT": "/ros/strawberry_ros_faces_module",
        }
        self.assertEqual(expected, preflight.FACE_ENVIRONMENT)

    def test_low_level_face_override_fails(self) -> None:
        self.configs["perception"]["services"]["faces"]["environment"][
            "FACES_RECOGNITION_THRESHOLD"
        ] = "0.75"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("FACES_RECOGNITION_THRESHOLD" in error for error in errors), errors
        )

    def test_direct_face_parameter_override_fails(self) -> None:
        self.configs["perception"]["services"]["faces"]["environment"][
            "HARU_PARAM__RECOGNITION_THRESHOLD"
        ] = "0.75"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("HARU_PARAM__RECOGNITION_THRESHOLD" in error for error in errors),
            errors,
        )

    def test_skeleton_policy_is_not_duplicated_in_compose(self) -> None:
        self.assertEqual({}, preflight.SKELETON_ENVIRONMENT)

    def test_low_level_skeleton_override_fails(self) -> None:
        self.configs["perception"]["services"]["skeletons"]["environment"][
            "SKELETONS_INFERENCE_REUSE_SIMILARITY_THRESHOLD"
        ] = "0.006"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any(
                "SKELETONS_INFERENCE_REUSE_SIMILARITY_THRESHOLD" in error
                for error in errors
            ),
            errors,
        )

    def test_direct_skeleton_parameter_map_override_fails(self) -> None:
        self.configs["perception"]["services"]["skeletons"]["environment"][
            "HARU_PARAM_MAP__BBOX_TRACK_MATCH_DISTANCE_NORM"
        ] = "EXTERNAL_DISTANCE"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any(
                "HARU_PARAM_MAP__BBOX_TRACK_MATCH_DISTANCE_NORM" in error
                for error in errors
            ),
            errors,
        )

    def test_playback_mount_mismatch_fails(self) -> None:
        self.configs["all"]["services"]["belief"]["volumes"][1]["source"] = str(
            self.base / "wrong-playback"
        )
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("playback registry root" in error for error in errors), errors
        )

    def test_local_image_fails(self) -> None:
        self.configs["perception"]["services"]["faces"]["image"] = "faces:local"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("image must come from" in error for error in errors), errors
        )

    def test_local_skeleton_image_fails(self) -> None:
        self.configs["perception"]["services"]["skeletons"][
            "image"
        ] = "local/skeletons:stale"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("skeletons image must come from" in error for error in errors),
            errors,
        )

    def test_local_azure_kinect_image_fails(self) -> None:
        self.configs["perception"]["services"]["azure-kinect"][
            "image"
        ] = "local/azure-kinect:stale"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("azure-kinect image must come from" in error for error in errors),
            errors,
        )

    def test_mutable_image_must_pull_on_start(self) -> None:
        self.configs["all"]["services"]["belief"]["pull_policy"] = "missing"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(any("pull_policy" in error for error in errors), errors)

    def test_skeleton_image_must_pull_on_start(self) -> None:
        self.configs["all"]["services"]["skeletons"]["pull_policy"] = "missing"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("skeletons pull_policy" in error for error in errors), errors
        )

    def test_azure_kinect_image_must_pull_on_start(self) -> None:
        self.configs["all"]["services"]["azure-kinect"]["pull_policy"] = "missing"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("azure-kinect pull_policy" in error for error in errors), errors
        )

    def test_azure_kinect_image_participates_in_cross_stack_signature(self) -> None:
        self.configs["all"]["services"]["azure-kinect"][
            "image"
        ] = "ghcr.io/haru-project/strawberry-ros-azure-kinect:other-tested"

        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)

        self.assertTrue(any("[cross-stack]" in error for error in errors), errors)

    def test_viz_topic_prefix_must_match_ros_prefix(self) -> None:
        self.configs["perception"]["services"]["faces"]["environment"][
            "HARU_TOPIC_PREFIX"
        ] = "/demo"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("VITE_ROS_TOPIC_PREFIX" in error for error in errors), errors
        )

    def test_viz_runtime_topic_prefix_environment_is_required(self) -> None:
        del self.configs["perception"]["services"]["viz"]["environment"][
            "VITE_ROS_TOPIC_PREFIX"
        ]
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("VITE_ROS_TOPIC_PREFIX" in error for error in errors), errors
        )

    def test_viz_must_not_shadow_the_ci_image_application_tree(self) -> None:
        viz = self.configs["perception"]["services"]["viz"]
        viz["environment"]["HARU_VIZ_REPO_ROOT"] = "/workspace/haru-viz"
        viz["working_dir"] = "/workspace/haru-viz"
        viz["volumes"].append(
            _bind(self.repo_root.parent / "haru-viz", "/workspace/haru-viz")
        )

        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)

        self.assertTrue(any("HARU_VIZ_REPO_ROOT" in error for error in errors), errors)
        self.assertTrue(any("working_dir" in error for error in errors), errors)
        self.assertTrue(
            any("shadows the application" in error for error in errors), errors
        )

    def test_prefixed_face_and_skeleton_identity_topics_stay_aligned(self) -> None:
        for config in self.configs.values():
            services = config["services"]
            services["faces"]["environment"]["HARU_TOPIC_PREFIX"] = "/robot_1"
            skeleton_environment = services["skeletons"]["environment"]
            skeleton_environment["HARU_TOPIC_PREFIX"] = "/robot_1"
            for key, suffix in preflight.SKELETON_PREFIXED_TOPIC_SUFFIXES.items():
                skeleton_environment[key] = f"/robot_1{suffix}"
            services["viz"]["environment"]["VITE_ROS_TOPIC_PREFIX"] = "/robot_1"

        self.assertEqual(
            [], preflight.validate_rendered_configs(self.configs, self.repo_root)
        )

        self.configs["perception"]["services"]["skeletons"]["environment"][
            "SKELETONS_FACES_TOPIC"
        ] = "/perception/proc/faces"
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("SKELETONS_FACES_TOPIC" in error for error in errors), errors
        )

    def test_topic_prefix_must_be_absolute_and_canonical(self) -> None:
        for invalid in ("robot_1", "/robot_1/"):
            configs = copy.deepcopy(self.configs)
            for config in configs.values():
                services = config["services"]
                services["faces"]["environment"]["HARU_TOPIC_PREFIX"] = invalid
                services["skeletons"]["environment"]["HARU_TOPIC_PREFIX"] = invalid
                services["viz"]["environment"]["VITE_ROS_TOPIC_PREFIX"] = invalid
            errors = preflight.validate_rendered_configs(configs, self.repo_root)
            self.assertTrue(
                any("HARU_TOPIC_PREFIX must be" in error for error in errors), errors
            )

    def test_persistent_bind_must_not_auto_create_host_path(self) -> None:
        self.configs["perception"]["services"]["faces"]["volumes"][0]["bind"][
            "create_host_path"
        ] = True
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("create_host_path=false" in error for error in errors), errors
        )

    def test_explicit_legacy_data_root_is_allowed(self) -> None:
        legacy_root = self.repo_root / "data" / "perception"
        for config in self.configs.values():
            services = config["services"]
            services["faces"]["volumes"][0]["source"] = str(legacy_root)
            services["belief"]["volumes"][0]["source"] = str(legacy_root)

        self.assertEqual(
            [], preflight.validate_rendered_configs(self.configs, self.repo_root)
        )

    def test_malformed_skeleton_environment_is_reported(self) -> None:
        self.configs["perception"]["services"]["skeletons"]["environment"] = None
        errors = preflight.validate_rendered_configs(self.configs, self.repo_root)
        self.assertTrue(
            any("skeletons environment is missing" in error for error in errors),
            errors,
        )

    def test_legacy_warning_is_read_only(self) -> None:
        marker = self.repo_root / "data" / "perception" / "gallery" / "face_gallery.npz"
        marker.parent.mkdir(parents=True)
        marker.write_bytes(b"gallery")
        before = marker.read_bytes()

        warning = preflight.legacy_state_migration_warning(
            self.repo_root, self.data_root
        )

        self.assertIsNotNone(warning)
        self.assertIn("No files were copied or modified", warning)
        self.assertEqual(before, marker.read_bytes())
        self.assertFalse(self.data_root.exists())

    def test_legacy_warning_stops_after_explicit_copy(self) -> None:
        legacy_marker = (
            self.repo_root / "data" / "perception" / "gallery" / "face_gallery.npz"
        )
        selected_marker = self.data_root / "gallery" / "face_gallery.npz"
        legacy_marker.parent.mkdir(parents=True)
        selected_marker.parent.mkdir(parents=True)
        legacy_marker.write_bytes(b"legacy")
        selected_marker.write_bytes(b"selected")

        self.assertIsNone(
            preflight.legacy_state_migration_warning(self.repo_root, self.data_root)
        )


if __name__ == "__main__":
    unittest.main()
