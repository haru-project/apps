#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/tts

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

# Determine the TTS image tag from docker-compose-tts.yaml (tts-client and gpt-sovits services)
TTS_COMPOSE_FILE="$DIR/../apps/docker-compose-tts.yaml"
if [[ -f "$TTS_COMPOSE_FILE" ]]; then
  IMAGE_TAG=$(awk '/^  tts-client:/ {found=1} found && /image:/ {gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2; exit}' "$TTS_COMPOSE_FILE")
  API_IMAGE_TAG=$(awk '/^  gpt-sovits:/ {found=1} found && /image:/ {gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2; exit}' "$TTS_COMPOSE_FILE")
fi
if [[ -z "${IMAGE_TAG:-}" ]]; then
  IMAGE_TAG="ghcr.io/haru-project/strawberry-tts:ros2"
fi
if [[ -z "${API_IMAGE_TAG:-}" ]]; then
  API_IMAGE_TAG="ghcr.io/haru-project/strawberry-tts-api:v0.2.1"
fi
if [[ -z "${API_IMAGE_TAG:-}" ]]; then
  IMAGE_TAG="ghcr.io/haru-project/strawberry-tts-api"
fi

mkdir -p "$DATA_FOLDER/configs"
mkdir -p "$DATA_FOLDER/ref_audio"
mkdir -p "$DATA_FOLDER/GPT_weights_mixed"
mkdir -p "$DATA_FOLDER/SoVITS_weights_mixed"

# Voices data
copy_with_tar "$IMAGE_TAG" \
  /ros2_ws/src/strawberry_tts/configs \
  "$DATA_FOLDER/configs"
copy_with_tar "$IMAGE_TAG" \
  /ros2_ws/src/strawberry_tts/ref_audio \
  "$DATA_FOLDER/ref_audio"

curl -L --fail -o "$DATA_FOLDER/GPT_weights_mixed/haru_default_v2_Pro-e20.ckpt" \
    "https://www.dropbox.com/scl/fi/hy8lfa46tc7zvkdkuz5w8/haru_default_v2_Pro-e20.ckpt?rlkey=ir82s0ovvvs7ldcnc36ywj9id&st=g29r7b4g&dl=1" \
    || { echo "Download failed: haru_default_v2_Pro-e20.ckpt"; exit 1; }

curl -L --fail -o "$DATA_FOLDER/SoVITS_weights_mixed/haru_default_v2_ProPlus_e12_s492.pth" \
    "https://www.dropbox.com/scl/fi/t7tvg5h6cnpiz6vsf9io0/haru_default_v2_ProPlus_e12_s492.pth?rlkey=gbt0ldrz6ejw7rywi89ewziu3&st=0w3p20cz&dl=1" \
    || { echo "Download failed: haru_default_v2_ProPlus_e12_s492.pth"; exit 1; }

# GPT‑SoVITS phoneme dictionary hotfix
docker run --rm "$API_IMAGE_TAG" cat /workspace/GPT-SoVITS/GPT_SoVITS/text/engdict-hot.rep > "$DATA_FOLDER/configs/pronunciation_dict.rep"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
