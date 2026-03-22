#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="${ROOT_DIR}/apps"
COMMON_FILE="${APPS_DIR}/compose.common.yaml"

stacks=(
  "perception:envs/perception.env:docker-compose-perception.yaml"
  "speech:envs/speech.env:docker-compose-speech.yaml"
  "llm:envs/llm.env:docker-compose-llm.yaml"
  "reasoner:envs/reasoner.env:docker-compose-reasoner.yaml"
  "tts:envs/tts.env:docker-compose-tts.yaml"
  "simulator:envs/simulator.env:docker-compose-simulator.yaml"
  "user:envs/user.env:docker-compose-user.yaml"
  "all:envs/all.env:docker-compose-all.yaml"
)

for entry in "${stacks[@]}"; do
  IFS=":" read -r name env_path file_name <<< "${entry}"
  echo "Validating ${name}..."
  docker compose \
    -f "${COMMON_FILE}" \
    -f "${APPS_DIR}/${file_name}" \
    --env-file "${ROOT_DIR}/${env_path}" \
    config >/dev/null
done

echo "All compose files validated."
