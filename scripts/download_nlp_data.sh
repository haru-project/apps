#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/nlp

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

NLP_COMPOSE=(
  docker compose
  --project-name "haru-nlp-data-download-${BASHPID}"
  -f "${DIR}/../apps/docker-compose-nlp.yaml"
  --env-file "${DIR}/../envs/nlp-cpu.env"
  --profile cpu
)

cleanup_compose_project() {
  local status=$?
  trap - EXIT
  "${NLP_COMPOSE[@]}" down --remove-orphans >/dev/null || true
  exit "${status}"
}
trap cleanup_compose_project EXIT

"${NLP_COMPOSE[@]}" run --rm --no-deps \
  --entrypoint haru-nlp-core-download-models haru-nlp-server-cpu

# Model files are created by the root user in the downloader container. Repair
# their permissions through the same bind mount instead of relying on a
# host-side chmod that cannot modify root-owned files.
"${NLP_COMPOSE[@]}" run --rm --no-deps \
  --entrypoint chmod haru-nlp-server-cpu -R a+rwX /models
