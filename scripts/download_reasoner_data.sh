#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/reasoner

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

# Determine the reasoner image tag from docker-compose-reasoner.yaml (reasoner service)
REASONER_COMPOSE_FILE="$DIR/../apps/docker-compose-reasoner.yaml"
if [[ -f "$REASONER_COMPOSE_FILE" ]]; then
  IMAGE_TAG=$(awk '/^  reasoner:/ {found=1} found && /image:/ {gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2; exit}' "$REASONER_COMPOSE_FILE")
fi

mkdir -p "$DATA_FOLDER/tasks"
mkdir -p "$DATA_FOLDER/configs"
mkdir -p "$DATA_FOLDER/configs/params"
mkdir -p "$DATA_FOLDER/projector"

# Reasoner data
copy_with_tar "$IMAGE_TAG" \
/opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/examples/tasks \
"$DATA_FOLDER/tasks"
copy_with_tar "$IMAGE_TAG" \
/opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/config \
"$DATA_FOLDER/configs"
copy_with_tar "$IMAGE_TAG" \
/opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/params \
"$DATA_FOLDER/configs/params"
copy_with_tar "$IMAGE_TAG" \
/opt/ros/jazzy/workspace/install/share/behavior_tree_web_projector/examples/resources \
"$DATA_FOLDER/projector"

SOURCE_POSTPROCESSORS_CONFIG="$DIR/../../agent_reasoner/haru_agent_reasoner/params/postprocessors_params.yaml"
if [ -f "$SOURCE_POSTPROCESSORS_CONFIG" ]; then
  cp "$SOURCE_POSTPROCESSORS_CONFIG" "$DATA_FOLDER/configs/params/postprocessors_params.yaml"
fi

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
