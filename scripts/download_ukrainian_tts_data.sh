#!/usr/bin/env bash
set -euo pipefail
cache_dir="${HARU_UK_TTS_DATA_DIR:-${HOME}/haru-tts-cache/ukrainian}"
mkdir -p "${cache_dir}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/download_helpers.sh"
image="$(compose_service_image "$DIR/../apps/docker-compose-tts.yaml" "$DIR/../envs/tts.env" tts-client)"
docker run --rm --entrypoint /opt/ukrainian-venv/bin/python -e HF_HOME=/tts/ukrainian/hf --user "$(id -u):$(id -g)" \
    -v "${cache_dir}:/tts/ukrainian:rw" \
    "$image" \
    -m strawberry_tts.ukrainian.provision
touch "${cache_dir}/.provisioned"
