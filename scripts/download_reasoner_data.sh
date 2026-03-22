#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/reasoner

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

mkdir -p "$DATA_FOLDER/tasks"
mkdir -p "$DATA_FOLDER/configs"
mkdir -p "$DATA_FOLDER/configs/params"
mkdir -p "$DATA_FOLDER/projector"

# Reasoner data
copy_with_tar ghcr.io/haru-project/haru-agent-reasoner:feature-web-projector \
  /opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/examples/tasks \
  "$DATA_FOLDER/tasks"
copy_with_tar ghcr.io/haru-project/haru-agent-reasoner:feature-web-projector \
  /opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/config \
  "$DATA_FOLDER/configs"
copy_with_tar ghcr.io/haru-project/haru-agent-reasoner:feature-web-projector \
  /opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/params \
  "$DATA_FOLDER/configs/params"
copy_with_tar ghcr.io/haru-project/haru-agent-reasoner:feature-web-projector \
  /opt/ros/jazzy/workspace/install/share/behavior_tree_unity_projector/examples/resources \
  "$DATA_FOLDER/projector"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
