from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

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
        exclude_channels: []
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

/**/speech_to_text:
  ros__parameters:
    # Preserve this comment while replacing the stale image default.
    min_segment_silent_ms: 300  # stale apps override
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
    assert "active_channel_warmup_secs: 0.3" in first_result
    assert "exclude_channels: [10, 11]" in first_result
    assert "# Preserve this comment" in first_result
    assert "min_segment_silent_ms: 800  # stale apps override" in first_result


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


def test_stop_enables_every_compose_profile() -> None:
    stop_script = (ROOT / "stop.sh").read_text()
    compose_down_lines = [
        line
        for line in stop_script.splitlines()
        if "scripts/compose.sh" in line and line.endswith(" down")
    ]
    assert compose_down_lines
    assert all('--profile "*" down' in line for line in compose_down_lines)
    assert "docker system prune" not in stop_script
