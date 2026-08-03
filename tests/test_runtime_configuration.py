from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_robot_domain_is_wired_through_canonical_override() -> None:
    fallback = "${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}}"
    assert fallback in (ROOT / "apps/compose.common.yaml").read_text()
    assert fallback in (ROOT / "apps/docker-compose-all.yaml").read_text()
    assert fallback in (ROOT / "apps/docker-compose-memory.yaml").read_text()
    assert fallback in (ROOT / "apps/docker-compose-timeline-player.yaml").read_text()


def test_persons_bridge_matches_reliable_source() -> None:
    bridge_config = (ROOT / "config/domain_bridge.yaml").read_text()
    persons_config = bridge_config.split(
        "  /perception/fusion/persons:\n", maxsplit=1
    )[1].split("\n  /perception/fusion/speech_sources:", maxsplit=1)[0]
    assert "remap:" not in persons_config
    assert "reliability: reliable" in persons_config
    assert "durability: volatile" in persons_config
    assert "history: keep_last" in persons_config
    assert "depth: 1" in persons_config

    bridge_compose = (ROOT / "apps/docker-compose-domain-bridge.yaml").read_text()
    all_compose = (ROOT / "apps/docker-compose-all.yaml").read_text()
    assert "persons-qos-relay" not in bridge_compose
    assert "persons-qos-relay" not in all_compose


def test_downloaders_handle_profiled_and_root_owned_data() -> None:
    speech_downloader = (ROOT / "scripts/download_speech_data.sh").read_text()
    assert '--entrypoint chmod' in speech_downloader
    assert 'chmod -R a+rwX "$MODELS_FOLDER"' not in speech_downloader

    nlp_downloader = (ROOT / "scripts/download_nlp_data.sh").read_text()
    assert "--profile cpu" in nlp_downloader
    assert "--no-deps" in nlp_downloader
    assert "haru-nlp-server-cpu" in nlp_downloader
    assert "haru-nlp-server\n" not in nlp_downloader
    assert "--entrypoint chmod" in nlp_downloader
    assert '--project-name "haru-nlp-data-download-${BASHPID}"' in nlp_downloader
    assert "down --remove-orphans" in nlp_downloader


def test_speech_configurator_accepts_already_updated_upstream_values(
    tmp_path: Path,
) -> None:
    config = tmp_path / "haru_speech.yaml"
    config.write_text(
        """/**/speech_stack:
  ros__parameters:
    sources:
      - source_id: "mic_0"
        detect_active_channels: true  # now enabled upstream
        process_active_channels_only: true
        dynamic_capture_controlled: true
        active_channel_rms_threshold: 0.003
        # An upstream comment used to break the multiline replacement.
        active_channel_warmup_secs: 2.0
        exclude_channels: [10, 11]
      - source_id: "mic_1"
        enabled: false
        capture_enabled: false
        speech_enabled: false
        localization_enabled: false

/**/audio_monitor:
  ros__parameters:
    capture_device: "zoom_h8"
    source_id: "mic_0"
    input_topic: "/perception/sensor/audio/zoom_h8"
    detect_active_channels: true
    # Keep comments and tolerate non-adjacent policy settings.
    active_channel_rms_threshold: 0.003
    active_channel_warmup_secs: 2.0
""",
        encoding="utf-8",
    )
    configurator = ROOT / "scripts/configure_speech_data.py"

    subprocess.run([sys.executable, configurator, config], check=True)
    first_result = config.read_text(encoding="utf-8")
    subprocess.run([sys.executable, configurator, config], check=True)

    assert config.read_text(encoding="utf-8") == first_result
    assert "# now enabled upstream" in first_result
    assert "# An upstream comment" in first_result


def test_image_downloader_includes_profiled_speech_base_image(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env bash
if [[ " $* " == *" --profile monolithic "* ]]; then
    printf '%s\n' 'ghcr.io/haru-project/haru-speech-base:test'
fi
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"

    result = subprocess.run(
        [ROOT / "scripts/download_all_images.sh", "--dry-run", "speech"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        env=environment,
    )

    assert "  ghcr.io/haru-project/haru-speech-base:test\n" in result.stdout


def test_stop_delegates_to_scoped_configurator_teardown() -> None:
    stop_script = (ROOT / "stop.sh").read_text()
    assert 'setup.sh" down "$@"' in stop_script
    assert "docker system prune" not in stop_script


def test_compose_validation_separates_defaults_from_generated_overrides() -> None:
    validator = (ROOT / "scripts/validate_compose.sh").read_text()

    assert "export HARU_COMPOSE_IGNORE_LOCAL_CONFIG=true" in validator
    assert "Validating configured ${stack}" in validator
    assert "HARU_COMPOSE_IGNORE_LOCAL_CONFIG=false" in validator


def test_setup_forwards_host_docker_registry_credentials() -> None:
    launcher = (ROOT / "setup.sh").read_text()

    assert 'scripts/prepare_docker_auth.py"' in launcher
    assert '${runtime_docker_dir}:/tmp/haru-home/.docker"' in launcher
    assert "HARU_GITHUB_TOKEN_FILE=/tmp/haru-home/.docker/github-token" in launcher
    assert "trap cleanup_runtime_auth EXIT" in launcher
    assert '"${ROOT_DIR}/scripts/ensure_ghcr_access.sh"' not in launcher
    assert '[[ "${needs_registry_auth}" == true ]]' in launcher
    assert '[[ "${requested_command}" == "up" ]]' in launcher
    assert '! has_arg --dry-run "$@"' in launcher


def test_setup_reuses_a_matching_local_configurator_image() -> None:
    launcher = (ROOT / "setup.sh").read_text()

    assert "using the matching local image" in launcher
    assert 'image_schema "${LOCAL_IMAGE}"' in launcher


def test_portable_docker_config_keeps_only_ghcr_auth(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    destination = tmp_path / "runtime" / "config.json"
    source.write_text(
        json.dumps(
            {
                "auths": {
                    "ghcr.io": {"auth": base64.b64encode(b"user:token").decode()},
                    "nvcr.io": {"auth": "must-not-be-forwarded"},
                },
                "credsStore": "desktop",
                "credHelpers": {"ghcr.io": "secretservice"},
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [ROOT / "scripts/prepare_docker_auth.py", source, destination],
        check=True,
    )

    prepared = json.loads(destination.read_text(encoding="utf-8"))
    assert prepared == {"auths": {"ghcr.io": {"auth": base64.b64encode(b"user:token").decode()}}}
    assert destination.stat().st_mode & 0o777 == 0o600


def test_portable_docker_config_extracts_credential_helper_auth(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    helper = fake_bin / "docker-credential-test"
    helper.write_text(
        """#!/usr/bin/env bash
read -r server
[[ "$1" == "get" && "$server" == "ghcr.io" ]]
printf '%s\n' '{"Username":"helper-user","Secret":"helper-token"}'
""",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    source = tmp_path / "source.json"
    destination = tmp_path / "config.json"
    source.write_text('{"credsStore":"test"}\n', encoding="utf-8")
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"

    subprocess.run(
        [ROOT / "scripts/prepare_docker_auth.py", source, destination],
        check=True,
        env=environment,
    )

    prepared = json.loads(destination.read_text(encoding="utf-8"))
    encoded = prepared["auths"]["ghcr.io"]["auth"]
    assert base64.b64decode(encoded).decode() == "helper-user:helper-token"


def test_registry_preflight_uses_existing_credentials_before_github_cli() -> None:
    preflight = (ROOT / "scripts/ensure_ghcr_access.sh").read_text()

    access_check = preflight.index("if registry_access_works; then")
    github_fallback = preflight.index("if login_with_gh && registry_access_works; then")
    interactive_fallback = preflight.index(
        "if login_interactively && registry_access_works; then"
    )

    assert access_check < github_fallback < interactive_fallback
    assert 'docker manifest inspect "${CHECK_IMAGE}"' in preflight
    assert "gh auth token --hostname github.com" in preflight
    assert "--password-stdin" in preflight
    assert "GitHub token with read:packages access" in preflight
    assert "Unable to access the private Haru image" in preflight
    assert "gh auth refresh --hostname github.com --scopes read:packages" in preflight


def test_registry_preflight_authenticates_with_github_cli(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    authenticated = tmp_path / "authenticated"
    docker_log = tmp_path / "docker.log"

    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "${FAKE_DOCKER_LOG}"
if [[ "$1 $2" == "manifest inspect" ]]; then
  [[ -f "${FAKE_AUTHENTICATED}" ]]
elif [[ "$1" == "login" ]]; then
  [[ "$(cat)" == "test-token" ]]
  touch "${FAKE_AUTHENTICATED}"
fi
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        """#!/usr/bin/env bash
if [[ "$1 $2" == "api user" ]]; then
  printf '%s\\n' test-user
elif [[ "$1 $2" == "auth token" ]]; then
  printf '%s\\n' test-token
else
  exit 1
fi
""",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
            "FAKE_AUTHENTICATED": str(authenticated),
            "FAKE_DOCKER_LOG": str(docker_log),
            "HARU_REGISTRY_CHECK_IMAGE": "ghcr.io/haru-project/private:test",
        }
    )
    result = subprocess.run(
        [ROOT / "scripts/ensure_ghcr_access.sh"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert authenticated.exists()
    assert "Authenticated to ghcr.io using the GitHub CLI account." in result.stderr
    assert docker_log.read_text().count("manifest inspect") == 2
    assert "login ghcr.io --username test-user --password-stdin" in docker_log.read_text()


def test_registry_preflight_uses_staged_github_cli_token(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    authenticated = tmp_path / "authenticated"
    token_file = tmp_path / "github-token"
    token_file.write_text("staged-token\n", encoding="utf-8")

    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env bash
if [[ "$1 $2" == "manifest inspect" ]]; then
  [[ -f "${FAKE_AUTHENTICATED}" ]]
elif [[ "$1" == "login" ]]; then
  [[ "$*" == *"--username staged-user"* ]]
  [[ "$(cat)" == "staged-token" ]]
  touch "${FAKE_AUTHENTICATED}"
fi
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
            "FAKE_AUTHENTICATED": str(authenticated),
            "HARU_GITHUB_USER": "staged-user",
            "HARU_GITHUB_TOKEN_FILE": str(token_file),
        }
    )

    result = subprocess.run(
        [ROOT / "scripts/ensure_ghcr_access.sh"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert authenticated.exists()
    assert "GitHub CLI account staged-user" in result.stderr


def test_registry_preflight_reports_noninteractive_authentication_failure(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    for command in ("docker", "gh"):
        executable = fake_bin / command
        executable.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
        executable.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    result = subprocess.run(
        [ROOT / "scripts/ensure_ghcr_access.sh"],
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 1
    assert "Unable to access the private Haru image" in result.stderr
    assert "gh auth login --hostname github.com" in result.stderr
    assert "read:packages" in result.stderr
