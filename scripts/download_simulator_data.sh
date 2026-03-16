#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/simulator

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

mkdir -p "$DATA_FOLDER/resources"

# Simulator data
copy_with_tar ghcr.io/haru-project/hve-simulator:feature-ci \
  /ros2_ws/src/haru2_core/resources \
  "$DATA_FOLDER/resources"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
