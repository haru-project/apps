#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT_DIR}/scripts/demo_language.sh"
bash "${ROOT_DIR}/scripts/build_multilingual.sh"
source "${ROOT_DIR}/scripts/download_helpers.sh"
python3 "${ROOT_DIR}/scripts/configure_llm_auth.py" "${ROOT_DIR}/envs/llm.secrets.env"

# Preserve hardware settings and saved tasks; initialize only missing bundles.
if [[ ! -f "${ROOT_DIR}/data/speech/configs/haru_speech.yaml" ]]; then
    TAR_OPTIONS=--skip-old-files copy_with_tar haru-asr:multilingual /opt/ros/jazzy/workspace/install/share/haru_speech/configs "${ROOT_DIR}/data/speech/configs"
    python3 "${ROOT_DIR}/scripts/configure_speech_data.py" "${ROOT_DIR}/data/speech/configs/haru_speech.yaml"
fi
if [[ ! -f "${ROOT_DIR}/data/llm/configs/haru_llm.yaml" ]]; then
    TAR_OPTIONS=--skip-old-files copy_with_tar haru-llm:multilingual /opt/ros/jazzy/workspace/install/share/haru_llm_ros/configs "${ROOT_DIR}/data/llm/configs"
fi
if [[ ! -d "${ROOT_DIR}/data/llm/agents" ]]; then
    TAR_OPTIONS=--skip-old-files copy_with_tar haru-llm:multilingual /opt/ros/jazzy/workspace/install/share/haru_llm_ros/agents "${ROOT_DIR}/data/llm/agents"
fi
if [[ ! -f "${ROOT_DIR}/data/reasoner/configs/world_models/haru_model.pddl" ]]; then
    TAR_OPTIONS=--skip-old-files copy_with_tar haru-reasoner:multilingual /opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/config "${ROOT_DIR}/data/reasoner/configs"
    TAR_OPTIONS=--skip-old-files copy_with_tar haru-reasoner:multilingual /opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/params "${ROOT_DIR}/data/reasoner/configs/params"
fi
if [[ ! -f "${ROOT_DIR}/data/tts/weight_refs_mixed.json" ]]; then
    staging=$(mktemp -d "${ROOT_DIR}/.runtime/tts.XXXXXX")
    trap 'rm -rf "$staging"' EXIT
    HARU_TTS_DATA_DIR="$staging" bash "${ROOT_DIR}/scripts/download_tts_data.sh"
    mkdir -p "${ROOT_DIR}/data/tts"
    cp -an "$staging/." "${ROOT_DIR}/data/tts/"
fi
if [[ ! -d "${ROOT_DIR}/data/tts/voice_gestures" ]]; then
    TAR_OPTIONS=--skip-old-files copy_with_tar haru-tts:multilingual /ros2_ws/src/strawberry_tts/voice_gestures "${ROOT_DIR}/data/tts/voice_gestures"
fi
if [[ "$HARU_DEMO_LANGUAGE" == uk-UA && ! -f "${HARU_UK_TTS_DATA_DIR:-${HOME}/haru-tts-cache/ukrainian}/.provisioned" ]]; then
    bash "${ROOT_DIR}/scripts/download_ukrainian_tts_data.sh"
fi
