#!/usr/bin/env bash
set -euo pipefail
cache_dir="${HARU_UK_TTS_DATA_DIR:-${HOME}/haru-tts-cache/ukrainian}"
mkdir -p "${cache_dir}"
docker run --rm --user "$(id -u):$(id -g)" \
    -v "${cache_dir}:/tts/ukrainian:rw" \
    "${HARU_UK_TTS_IMAGE:-ghcr.io/haru-project/strawberry-tts@sha256:a11e16806685cb0514702b392d9cbc0ffe5823f089970415bb0e8bd30cd2a020}" \
    -m strawberry_tts.ukrainian.provision
touch "${cache_dir}/.provisioned"
