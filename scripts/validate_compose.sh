#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="${ROOT_DIR}/apps"

stacks=(
  "domain-bridge:envs/domain-bridge.env:docker-compose-domain-bridge.yaml:"
  "perception:envs/perception.env:docker-compose-perception.yaml:"
  "speech:envs/speech.env:docker-compose-speech.yaml:"
  "llm:envs/llm.env:docker-compose-llm.yaml:"
  "reasoner:envs/reasoner.env:docker-compose-reasoner.yaml:"
  "tts:envs/tts.env:docker-compose-tts.yaml:"
  "simulator:envs/simulator.env:docker-compose-simulator.yaml:"
  "ipad:envs/ipad.env:docker-compose-ipad.yaml:"
  "projector:envs/projector.env:docker-compose-projector.yaml:"
  "user:envs/user.env:docker-compose-user.yaml:"
  "nlp-cpu:envs/nlp-cpu.env:docker-compose-nlp.yaml:cpu"
  "nlp-gpu:envs/nlp-gpu.env:docker-compose-nlp.yaml:gpu"
  "timeline-player:envs/timeline-player.env:docker-compose-timeline-player.yaml:"
  "memory:envs/memory.env:docker-compose-memory.yaml:"
  "all-cpu:envs/all.env:docker-compose-all.yaml:cpu"
  "all-gpu:envs/all.env:docker-compose-all.yaml:gpu"
)

for entry in "${stacks[@]}"; do
  IFS=":" read -r name env_path file_names profiles <<< "${entry}"
  echo "Validating ${name}..."
  cmd=(docker compose)
  IFS="," read -ra files <<< "${file_names}"
  for file_name in "${files[@]}"; do
    cmd+=(-f "${APPS_DIR}/${file_name}")
  done
  cmd+=(--env-file "${ROOT_DIR}/${env_path}" config)
  if [[ -n "${profiles}" ]]; then
    COMPOSE_PROFILES="${profiles}" "${cmd[@]}" >/dev/null
  else
    "${cmd[@]}" >/dev/null
  fi
done

core_services="$(
  HARU_NLP_SERVER_GPU_ENABLED=false \
    HARU_DEPLOYMENT=physical \
    bash "${ROOT_DIR}/scripts/compose.sh" all config --services
)"
for required in \
  gpt-sovits cerevoice-api tts-client ros-node \
  audio recognition verification localization \
  server action-args agent-memory reasoner context-manager bt-forest \
  nlp-redis haru-nlp-server-cpu
do
  if ! grep -qx "${required}" <<< "${core_services}"; then
    echo "Core all stack is missing ${required}." >&2
    exit 1
  fi
done

for excluded in \
  base audio-capture-manager dashboard webui vllm \
  unity-app web-server ipad-server projector-server episode-builder \
  execute-task-scenario execute-task-test timeline-player timeline-player-dev \
  haru-nlp-server-gpu agent-memory-dashboard
do
  if grep -qx "${excluded}" <<< "${core_services}"; then
    echo "Core all stack unexpectedly enables ${excluded}." >&2
    exit 1
  fi
done

simulator_services="$(
  HARU_NLP_SERVER_GPU_ENABLED=false \
    HARU_DEPLOYMENT=simulator \
    bash "${ROOT_DIR}/scripts/compose.sh" all config --services
)"
for required in unity-app web-server; do
  grep -qx "${required}" <<< "${simulator_services}" || {
    echo "Simulator all stack is missing ${required}." >&2
    exit 1
  }
done
for excluded in azure-kinect skeletons faces; do
  if grep -qx "${excluded}" <<< "${simulator_services}"; then
    echo "Simulator all stack unexpectedly enables ${excluded}." >&2
    exit 1
  fi
done

echo "All compose files validated."
