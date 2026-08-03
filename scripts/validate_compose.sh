#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="${ROOT_DIR}/apps"
source "${ROOT_DIR}/scripts/download_helpers.sh"
unset \
  COMPOSE_PROFILES \
  HARU_ROBOT_ROS_DOMAIN_ID \
  HARU_PERCEPTION_ROS_DOMAIN_ID \
  ROS_DOMAIN_ID \
  FROM_DOMAIN_ID \
  TO_DOMAIN_ID

stacks=(
  "domain-bridge:envs/domain-bridge.env:docker-compose-domain-bridge.yaml:"
  "perception:envs/perception.env:docker-compose-perception.yaml:"
  "speech:envs/speech.env:docker-compose-speech.yaml:"
  "llm:envs/llm.env:docker-compose-llm.yaml:"
  "reasoner:envs/reasoner.env:docker-compose-reasoner.yaml:"
  "tts:envs/tts.env:docker-compose-tts.yaml:all"
  "simulator:envs/simulator.env:docker-compose-simulator.yaml:"
  "ipad:envs/ipad.env:docker-compose-ipad.yaml:"
  "projector:envs/projector.env:docker-compose-projector.yaml:"
  "user:envs/user.env:docker-compose-user.yaml:"
  "nlp-cpu:envs/nlp-cpu.env:docker-compose-nlp.yaml:cpu"
  "nlp-gpu:envs/nlp-gpu.env:docker-compose-nlp.yaml:gpu"
  "timeline-player:envs/timeline-player.env:docker-compose-timeline-player.yaml:timeline-compat"
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

assert_equal() {
  local expected="$1"
  local actual="$2"
  local description="$3"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "${description}: expected '${expected}', got '${actual}'." >&2
    exit 1
  fi
}

compose_service_value() {
  local stack="$1"
  local service="$2"
  local variable="$3"
  bash "${ROOT_DIR}/scripts/compose.sh" "${stack}" config --format json "${service}" |
    python3 -c '
import json
import sys

service = json.load(sys.stdin)["services"][sys.argv[1]]
value = service.get("environment", {}).get(sys.argv[2])
if value is None:
    raise SystemExit(f"{sys.argv[2]} is not set for service {sys.argv[1]}")
print(value)
' "${service}" "${variable}"
}

# A positional service selector must resolve profiled services without relying
# on a caller-wide COMPOSE_PROFILES workaround.
tts_client_image="$(
  unset COMPOSE_PROFILES
  export STRAWBERRY_TTS_IMAGE=example.invalid/tts-client:profile-test
  compose_service_image \
    "${APPS_DIR}/docker-compose-tts.yaml" \
    "${ROOT_DIR}/envs/tts.env" \
    tts-client
)"
assert_equal \
  "example.invalid/tts-client:profile-test" \
  "${tts_client_image}" \
  "Profiled TTS client image resolution failed"

tts_api_image="$(
  unset COMPOSE_PROFILES
  export STRAWBERRY_TTS_API_IMAGE=example.invalid/gpt-sovits:profile-test
  compose_service_image \
    "${APPS_DIR}/docker-compose-tts.yaml" \
    "${ROOT_DIR}/envs/tts.env" \
    gpt-sovits
)"
assert_equal \
  "example.invalid/gpt-sovits:profile-test" \
  "${tts_api_image}" \
  "Profiled TTS API image resolution failed"

nlp_cpu_services="$(
  docker compose \
    -f "${APPS_DIR}/docker-compose-nlp.yaml" \
    --env-file "${ROOT_DIR}/envs/nlp-cpu.env" \
    --profile cpu \
    config --services
)"
grep -qx haru-nlp-server-cpu <<< "${nlp_cpu_services}" || {
  echo "NLP CPU profile does not expose haru-nlp-server-cpu." >&2
  exit 1
}
if grep -qx haru-nlp-server <<< "${nlp_cpu_services}"; then
  echo "NLP CPU profile unexpectedly exposes the obsolete haru-nlp-server service." >&2
  exit 1
fi

bash "${ROOT_DIR}/scripts/compose.sh" llm --profile dashboard config --format json dashboard |
  python3 -c '
import json
import sys

healthcheck = json.load(sys.stdin)["services"]["dashboard"]["healthcheck"]
command = " ".join(healthcheck["test"])
if "127.0.0.1:8501/_stcore/health" not in command:
    raise SystemExit("LLM dashboard healthcheck does not probe Streamlit over HTTP")
if "haru-ros-healthcheck" in command:
    raise SystemExit("LLM dashboard still inherits the image ROS healthcheck")
'

timeline_services="$(
  bash "${ROOT_DIR}/scripts/compose.sh" timeline-player config --services
)"
grep -qx timeline-player <<< "${timeline_services}" || {
  echo "Timeline Player wrapper did not select its compatibility profile." >&2
  exit 1
}
if grep -qx timeline-player-dev <<< "${timeline_services}"; then
  echo "Timeline Player wrapper unexpectedly selected the dev profile." >&2
  exit 1
fi
bash "${ROOT_DIR}/scripts/compose.sh" timeline-player config --format json timeline-player |
  python3 -c '
import json
import sys

healthcheck = json.load(sys.stdin)["services"]["timeline-player"]["healthcheck"]
if not any("bash -lc" in item for item in healthcheck["test"]):
    raise SystemExit("Timeline Player healthcheck does not run source through Bash")
'

timeline_image="$(
  docker compose \
    -f "${APPS_DIR}/docker-compose-timeline-player.yaml" \
    --env-file "${ROOT_DIR}/envs/timeline-player.env" \
    config --images timeline-player
)"
timeline_download_output="$(
  bash "${ROOT_DIR}/scripts/download_all_images.sh" --dry-run timeline-player
)"
grep -Fqx "  ${timeline_image}" <<< "${timeline_download_output}" || {
  echo "Timeline Player image download did not select the compatibility profile." >&2
  exit 1
}

# Standalone stacks must share one robot/application ROS domain while
# perception publishers remain isolated on their own domain.
for service_entry in \
  "tts:tts-client" \
  "llm:action-args" \
  "reasoner:bt-forest" \
  "memory:agent-memory" \
  "timeline-player:timeline-player"
do
  IFS=":" read -r stack service <<< "${service_entry}"
  assert_equal \
    "0" \
    "$(compose_service_value "${stack}" "${service}" ROS_DOMAIN_ID)" \
    "Default ROS domain for ${stack}/${service}"
  assert_equal \
    "26" \
    "$(HARU_ROBOT_ROS_DOMAIN_ID=26 compose_service_value "${stack}" "${service}" ROS_DOMAIN_ID)" \
    "Overridden ROS domain for ${stack}/${service}"
done

for service_entry in "perception:belief" "speech:recognition"; do
  IFS=":" read -r stack service <<< "${service_entry}"
  assert_equal \
    "200" \
    "$(HARU_ROBOT_ROS_DOMAIN_ID=26 compose_service_value "${stack}" "${service}" ROS_DOMAIN_ID)" \
    "Perception ROS domain for ${stack}/${service}"
  assert_equal \
    "201" \
    "$(HARU_PERCEPTION_ROS_DOMAIN_ID=201 compose_service_value "${stack}" "${service}" ROS_DOMAIN_ID)" \
    "Overridden perception ROS domain for ${stack}/${service}"
done

assert_equal \
  "200" \
  "$(HARU_ROBOT_ROS_DOMAIN_ID=26 compose_service_value domain-bridge domain-bridge FROM_DOMAIN_ID)" \
  "Domain bridge source domain"
assert_equal \
  "26" \
  "$(HARU_ROBOT_ROS_DOMAIN_ID=26 compose_service_value domain-bridge domain-bridge TO_DOMAIN_ID)" \
  "Domain bridge target domain"
assert_equal \
  "201" \
  "$(HARU_PERCEPTION_ROS_DOMAIN_ID=201 compose_service_value domain-bridge domain-bridge FROM_DOMAIN_ID)" \
  "Overridden domain bridge source domain"

for service_entry in \
  "all:action-args:26" \
  "all:bt-forest:26" \
  "all:agent-memory:26" \
  "all:belief:201" \
  "all:recognition:201"
do
  IFS=":" read -r stack service expected_domain <<< "${service_entry}"
  assert_equal \
    "${expected_domain}" \
    "$(HARU_ROBOT_ROS_DOMAIN_ID=26 HARU_PERCEPTION_ROS_DOMAIN_ID=201 compose_service_value "${stack}" "${service}" ROS_DOMAIN_ID)" \
    "All-in-one ROS domain for ${service}"
done
assert_equal \
  "201" \
  "$(HARU_ROBOT_ROS_DOMAIN_ID=26 HARU_PERCEPTION_ROS_DOMAIN_ID=201 compose_service_value all domain-bridge FROM_DOMAIN_ID)" \
  "All-in-one bridge source domain"
assert_equal \
  "26" \
  "$(HARU_ROBOT_ROS_DOMAIN_ID=26 HARU_PERCEPTION_ROS_DOMAIN_ID=201 compose_service_value all domain-bridge TO_DOMAIN_ID)" \
  "All-in-one bridge target domain"
assert_equal \
  "27" \
  "$(ROS_DOMAIN_ID=27 compose_service_value all action-args ROS_DOMAIN_ID)" \
  "Legacy all-in-one ROS domain fallback"

bash "${ROOT_DIR}/scripts/compose.sh" reasoner config --format json bt-forest |
  python3 -c '
import json
import sys

service = json.load(sys.stdin)["services"]["bt-forest"]
if "groot_monitor_enabled:=false" not in service["command"]:
    raise SystemExit("bt-forest enables the Groot GUI monitor by default")
'

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
