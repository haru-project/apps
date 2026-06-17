#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/tts

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

# Determine the TTS image tag from docker-compose-tts.yaml (tts-client service)
TTS_COMPOSE_FILE="$DIR/../apps/docker-compose-tts.yaml"
if [[ -f "$TTS_COMPOSE_FILE" ]]; then
  IMAGE_TAG=$(awk '/^  tts-client:/ {found=1} found && /image:/ {gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2; exit}' "$TTS_COMPOSE_FILE")
fi
if [[ -z "${IMAGE_TAG:-}" ]]; then
  IMAGE_TAG="ghcr.io/haru-project/strawberry-tts:ros2"
fi

mkdir -p "$DATA_FOLDER/configs"
mkdir -p "$DATA_FOLDER/ref_audio"

# Voices data
copy_with_tar "$IMAGE_TAG" \
  /ros2_ws/src/strawberry_tts/configs \
  "$DATA_FOLDER/configs"
copy_with_tar "$IMAGE_TAG" \
  /ros2_ws/src/strawberry_tts/ref_audio \
  "$DATA_FOLDER/ref_audio"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
