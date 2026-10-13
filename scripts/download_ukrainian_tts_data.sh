#!/usr/bin/env bash
set -euo pipefail
cache_dir="${HARU_UK_TTS_DATA_DIR:-${HOME}/haru-tts-cache/ukrainian}"
mkdir -p "${cache_dir}"
docker run --rm --user "$(id -u):$(id -g)" \
    -v "${cache_dir}:/tts/ukrainian:rw" \
    "${HARU_UK_TTS_IMAGE:-ghcr.io/haru-project/strawberry-tts:ukrainian-develop}" \
    -m strawberry_tts.ukrainian.provision
