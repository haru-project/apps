#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER="${DIR}/../data/memory"

source "${DIR}/download_helpers.sh"
cleanup_data_dir "${DATA_FOLDER}"

copy_with_tar ghcr.io/haru-project/agent-memory-ros:latest \
  /ws/install/agent_memory/share/agent_memory/config \
  "${DATA_FOLDER}/configs"

chmod -R a+rwX "${DATA_FOLDER}"
