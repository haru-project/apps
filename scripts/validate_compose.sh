#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="${ROOT_DIR}/apps"
ROBOT_ENV_FILE="${HARU_ROBOT_ENV_FILE:-${ROOT_DIR}/envs/robot.env}"

stacks=(
  "domain-bridge:envs/domain-bridge.env:docker-compose-domain-bridge.yaml:"
  "perception:envs/perception.env:docker-compose-perception.yaml:"
  "speech:envs/speech.env:docker-compose-speech.yaml:"
  "llm:envs/llm.env:docker-compose-llm.yaml:"
  "reasoner:envs/reasoner.env:docker-compose-reasoner.yaml:"
  "tts:envs/tts.env:docker-compose-tts.yaml:tts,ros"
  "simulator:envs/simulator.env:docker-compose-simulator.yaml:"
  "ipad:envs/ipad.env:docker-compose-ipad.yaml:"
  "projector:envs/projector.env:docker-compose-projector.yaml:"
  "user:envs/user.env:docker-compose-user.yaml:"
  "all:envs/all.env:docker-compose-all.yaml:"
)

for entry in "${stacks[@]}"; do
  IFS=":" read -r name env_path file_names profiles <<< "${entry}"
  echo "Validating ${name}..."
  cmd=(docker compose)
  IFS="," read -ra files <<< "${file_names}"
  for file_name in "${files[@]}"; do
    cmd+=(-f "${APPS_DIR}/${file_name}")
  done
  if [[ -f "${ROBOT_ENV_FILE}" ]]; then
    cmd+=(--env-file "${ROBOT_ENV_FILE}")
  fi
  cmd+=(--env-file "${ROOT_DIR}/${env_path}")
  if [[ -n "${profiles}" ]]; then
    COMPOSE_PROFILES="${profiles}" "${cmd[@]}" config --format json | python3 "${ROOT_DIR}/scripts/check_compose_domains.py"
  else
    "${cmd[@]}" config --format json | python3 "${ROOT_DIR}/scripts/check_compose_domains.py"
  fi
done

echo "All compose files validated."
