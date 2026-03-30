#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/simulator

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

mkdir -p "$DATA_FOLDER/resources"

# Simulator data
copy_with_tar ghcr.io/haru-project/hve-simulator@sha256:fb89b358b9c69ea34fedda4781d42158ef392af2ca96debb12d4344a8b81031d \
  /ros2_ws/src/haru2_core/resources \
  "$DATA_FOLDER/resources"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
