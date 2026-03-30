#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/speech

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

# Speech data
copy_with_tar ghcr.io/haru-project/haru-speech:ros2 \
  /opt/ros/jazzy/workspace/install/share/haru_speech_ros/configs \
  "$DATA_FOLDER/configs"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
