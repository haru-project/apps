#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/simulator

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

# Determine the simulator image tag from docker-compose-simulator.yaml (unity-app service)
SIM_COMPOSE_FILE="$DIR/../apps/docker-compose-simulator.yaml"
if [[ -f "$SIM_COMPOSE_FILE" ]]; then
  IMAGE_TAG=$(awk '/^  unity-app:/ {found=1} found && /image:/ {gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2; exit}' "$SIM_COMPOSE_FILE")
fi
if [[ -z "${IMAGE_TAG:-}" ]]; then
  IMAGE_TAG="ghcr.io/haru-project/hve-simulator@sha256:fb89b358b9c69ea34fedda4781d42158ef392af2ca96debb12d4344a8b81031d"
fi

mkdir -p "$DATA_FOLDER/resources"

# Simulator data
copy_with_tar "$IMAGE_TAG" \
  /ros2_ws/src/haru2_core/resources \
  "$DATA_FOLDER/resources"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
