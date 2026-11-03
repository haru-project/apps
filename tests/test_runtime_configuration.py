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


def test_microphone_context_bridge_is_profiled_and_reverses_configurable_domains() -> None:
    import xml.etree.ElementTree as ET
    import yaml

    forward = yaml.safe_load((ROOT / 'config/domain_bridge.yaml').read_text())
    reverse = yaml.safe_load((ROOT / 'config/microphone_context_bridge.yaml').read_text())
    assert not any(topic.startswith('/perception/proc/speech/asr/') for topic in forward['topics'])
    assert '/perception/proc/speech/control/state' not in forward['topics']
    assert '/perception/proc/speech/microphone_policy' not in reverse['topics']
    types = {route['type'] for config in (forward, reverse) for route in config['topics'].values()}
    assert not {'haru_speech_msgs/msg/MicrophonePolicy', 'haru_speech_msgs/msg/SpeechControlState'} & types
    assert reverse['name'] != forward['name']
    assert reverse['topics']['/haru_agent/attention_scope'] == {
        'type': 'haru_belief_msgs/msg/AttentionScope',
        'qos': {'reliability': 'reliable', 'durability': 'transient_local', 'history': 'keep_last', 'depth': 1},
    }
    assert reverse['topics']['/haru_agent/participant_scope'] == reverse['topics']['/haru_agent/attention_scope']
    assert forward['topics']['/perception/fusion/participant_scope/result'] == {
        'type': 'haru_belief_msgs/msg/ParticipantScopeResult',
        'qos': {'reliability': 'reliable', 'durability': 'transient_local', 'history': 'keep_last', 'depth': 10},
    }
    assert reverse['topics']['/haru_agent/microphone_management']['type'] == 'std_msgs/msg/String'
    assert reverse['topics']['/haru2/tts_status']['type'] == 'haru2_core_msgs/msg/TTSStatus'
    assert reverse['topics']['/haru2/tts_status']['qos']['durability'] == 'volatile'
    compose = yaml.safe_load((ROOT / 'apps/docker-compose-domain-bridge.yaml').read_text())
    service = compose['services']['microphone-context-bridge']
    assert service['profiles'] == ['demo-microphone-management']
    env = service['environment']
    assert env['FROM_DOMAIN_ID'].startswith('${HARU_ROBOT_ROS_DOMAIN_ID:')
    assert env['TO_DOMAIN_ID'].startswith('${HARU_PERCEPTION_ROS_DOMAIN_ID:')
    assert env['DOMAIN_BRIDGE_CONFIG'].endswith('/microphone_context_bridge.yaml')

    tree = ET.parse(ROOT / 'config/behavior_trees/simple_gaze_controller.xml')
    sequence = tree.find(".//Sequence[@name='GAZE_INDIVIDUAL']")
    assert sequence is not None
    assert sequence[0].attrib == {'output_key': 'selection_id', 'value': '$${GazeControllerSelectionId}'}
    concat = sequence.find("Action[@ID='Concatenate3Strings']")
    assert concat is not None and concat.attrib['first'] == '{selection_id}'
    assert concat.attrib['second'] == ':' and concat.attrib['string_3'] == '{track_person_id}'
    publish = sequence.find("Condition[@ID='PublishAutoStdString']")
    assert publish is not None and publish.attrib['topic_name'] == '/haru_agent/selected_participant'


def test_feature_image_overrides_are_opt_in() -> None:
    env = (ROOT / 'envs/demo-microphone-management.env').read_text()
    assert 'COMPOSE_PROFILES=demo-microphone-management' in env
    assert 'GAZE_CONTROLLER_FILE=demo_microphone_gaze_controller.xml' in env
    assert env.count(':feature-perception-attention') == 11
    assert 'PERCEPTION_DOMAIN_BRIDGE_IMAGE=ghcr.io/haru-project/haru-domain-bridge-jazzy:hotfix-perception-attention-interfaces' in env
    assert 'HARU_LLM_IMAGE=ghcr.io/haru-project/haru-llm:feature-perception-attention' in env
    compose = (ROOT / 'apps/docker-compose-reasoner.yaml').read_text()
    assert 'gaze_controller_file:=${GAZE_CONTROLLER_FILE:-simple_gaze_controller.xml}' in compose
    assert 'demo_microphone_gaze_controller.xml:ro' in compose


def test_reasoner_microphone_settings_survive_container_recreation() -> None:
    import yaml
    compose = yaml.safe_load((ROOT / 'apps/docker-compose-reasoner.yaml').read_text())
    service = compose['services']['reasoner']
    assert service['environment']['HARU_MICROPHONE_SETTINGS_FILE'] == '/shared/state/microphone_settings.json'
    assert '../data/reasoner/state:/shared/state:rw' in service['volumes']
