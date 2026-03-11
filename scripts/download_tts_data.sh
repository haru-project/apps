#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/tts

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

mkdir -p "$DATA_FOLDER/configs"
mkdir -p "$DATA_FOLDER/ref_audio"

# Voices data
copy_with_tar ghcr.io/haru-project/strawberry-tts:ros2 \
  /ros2_ws/src/strawberry_tts/configs \
  "$DATA_FOLDER/configs"
copy_with_tar ghcr.io/haru-project/strawberry-tts:ros2 \
  /ros2_ws/src/strawberry_tts/ref_audio \
  "$DATA_FOLDER/ref_audio"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
