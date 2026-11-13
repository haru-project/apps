#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/llm

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

COMPOSE_FILE="$DIR/../apps/docker-compose-llm.yaml"
IMAGE_TAG="$(compose_service_image "$COMPOSE_FILE" "$DIR/../envs/llm.env" action-args)"

# LLM data
copy_with_tar "$IMAGE_TAG" \
  /opt/ros/jazzy/workspace/install/share/haru_llm_ros/configs \
  "$DATA_FOLDER/configs"
copy_with_tar "$IMAGE_TAG" \
  /opt/ros/jazzy/workspace/install/share/haru_llm_ros/agents \
  "$DATA_FOLDER/agents"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
