#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/nlp

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

docker compose -f "${DIR}/../apps/docker-compose-nlp.yaml" --env-file "${DIR}/../envs/nlp-cpu.env" run --rm \
  --entrypoint haru-nlp-core-download-models haru-nlp-server

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
