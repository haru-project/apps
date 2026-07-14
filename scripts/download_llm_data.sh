#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/llm

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

COMPOSE_FILE="$DIR/../apps/docker-compose-llm.yaml"
if [[ -f "$COMPOSE_FILE" ]]; then
  IMAGE_TAG=$(
    docker compose \
      -f "$COMPOSE_FILE" \
      --env-file "$DIR/../envs/llm.env" \
      config --format json \
      | python3 -c 'import json, sys; print(json.load(sys.stdin)["services"]["action-args"]["image"])'
  )
fi
if [[ -z "${IMAGE_TAG:-}" ]]; then
  IMAGE_TAG="ghcr.io/haru-project/haru-llm:feature-context-fix"
fi

# LLM data
copy_with_tar "$IMAGE_TAG" \
  /opt/ros/jazzy/workspace/install/share/haru_llm_ros/configs \
  "$DATA_FOLDER/configs"
copy_with_tar "$IMAGE_TAG" \
  /opt/ros/jazzy/workspace/install/share/haru_llm_ros/agents \
  "$DATA_FOLDER/agents"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
