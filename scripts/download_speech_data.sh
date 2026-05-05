#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/speech

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

# Speech data
copy_with_tar "${HARU_SPEECH_BASE_IMAGE:-ghcr.io/haru-project/haru-speech-base:feature-asr-improve}" \
  /opt/ros/jazzy/workspace/install/share/haru_speech/configs \
  "$DATA_FOLDER/configs"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
