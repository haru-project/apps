#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/llm

source "${DIR}/download_helpers.sh"
cleanup_data_dir "$DATA_FOLDER"

# LLM data
copy_with_tar ghcr.io/haru-project/haru-llm:feature-eval-test \
  /opt/ros/jazzy/workspace/install/share/haru_llm_ros/configs \
  "$DATA_FOLDER/configs"
copy_with_tar ghcr.io/haru-project/haru-llm:feature-eval-test \
  /opt/ros/jazzy/workspace/install/share/haru_llm_ros/agents \
  "$DATA_FOLDER/agents"

# Give permissions
chmod -R a+rwX "$DATA_FOLDER"
