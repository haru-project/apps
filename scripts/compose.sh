#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="${ROOT_DIR}/apps"
ROBOT_ENV_FILE="${HARU_ROBOT_ENV_FILE:-${ROOT_DIR}/envs/robot.env}"

env_file_value() {
    local file_path="$1"
    local key="$2"
    if [[ ! -f "${file_path}" ]]; then
        return 0
    fi
    awk -F= -v key="${key}" '
        /^[[:space:]]*#/ { next }
        $1 == key {
            value = substr($0, index($0, "=") + 1)
            sub(/[[:space:]]+#.*$/, "", value)
            print value
        }
    ' "${file_path}" | tail -n 1
}

effective_env_value() {
    local file_path="$1"
    local key="$2"
    local override="${!key-}"
    if [[ -n "${override}" ]]; then
        printf '%s\n' "${override}"
        return
    fi
    env_file_value "${file_path}" "${key}"
}

ensure_domain_env_consistency() {
    local stack_name="$1"
    local stack_env_file="$2"

    case "${stack_name}" in
        speech)
            local speech_ros_domain
            local speech_perception_domain
            local perception_perception_domain
            speech_ros_domain="$(effective_env_value "${stack_env_file}" ROS_DOMAIN_ID)"
            speech_perception_domain="$(effective_env_value "${stack_env_file}" HARU_PERCEPTION_ROS_DOMAIN_ID)"
            perception_perception_domain="$(effective_env_value "${ROOT_DIR}/envs/perception.env" HARU_PERCEPTION_ROS_DOMAIN_ID)"
            if [[ -n "${speech_ros_domain}" && -n "${speech_perception_domain}" && "${speech_ros_domain}" != "${speech_perception_domain}" ]]; then
                echo "Invalid speech ROS domain config: effective ROS_DOMAIN_ID=${speech_ros_domain}, but speech must run on HARU_PERCEPTION_ROS_DOMAIN_ID=${speech_perception_domain}." >&2
                echo "Set both ROS_DOMAIN_ID and HARU_PERCEPTION_ROS_DOMAIN_ID in envs/speech.env, or in the shell environment, to the perception domain, usually 200." >&2
                exit 1
            fi
            if [[ -z "${HARU_PERCEPTION_ROS_DOMAIN_ID-}" && -n "${speech_perception_domain}" && -n "${perception_perception_domain}" && "${speech_perception_domain}" != "${perception_perception_domain}" ]]; then
                echo "Invalid perception domain config: envs/speech.env uses HARU_PERCEPTION_ROS_DOMAIN_ID=${speech_perception_domain}, but envs/perception.env uses ${perception_perception_domain}." >&2
                echo "Keep speech and perception on the same HARU_PERCEPTION_ROS_DOMAIN_ID, or export HARU_PERCEPTION_ROS_DOMAIN_ID explicitly for both launches." >&2
                exit 1
            fi
        ;;
    esac
}

stack="${1:-}"
if [[ -z "${stack}" ]]; then
    echo "Usage: $(basename "$0") <stack> <docker compose args...>" >&2
    echo "Stacks: domain-bridge | perception | speech | llm | reasoner | tts | simulator | ipad | projector | user | all" >&2
    exit 1
fi
shift

stack_files=()

case "${stack}" in
    domain-bridge)
        stack_files=("${APPS_DIR}/docker-compose-domain-bridge.yaml")
        env_file="${ROOT_DIR}/envs/domain-bridge.env"
    ;;
    perception)
        stack_files=("${APPS_DIR}/docker-compose-perception.yaml")
        env_file="${ROOT_DIR}/envs/perception.env"
    ;;
    speech)
        stack_files=("${APPS_DIR}/docker-compose-speech.yaml")
        env_file="${ROOT_DIR}/envs/speech.env"
    ;;
    llm)
        stack_files=("${APPS_DIR}/docker-compose-llm.yaml")
        env_file="${ROOT_DIR}/envs/llm.env"
    ;;
    reasoner)
        stack_files=("${APPS_DIR}/docker-compose-reasoner.yaml")
        env_file="${ROOT_DIR}/envs/reasoner.env"
    ;;
    tts)
        stack_files=("${APPS_DIR}/docker-compose-tts.yaml")
        env_file="${ROOT_DIR}/envs/tts.env"
    ;;
    simulator)
        stack_files=("${APPS_DIR}/docker-compose-simulator.yaml")
        env_file="${ROOT_DIR}/envs/simulator.env"
    ;;
    ipad)
        stack_files=("${APPS_DIR}/docker-compose-ipad.yaml")
        env_file="${ROOT_DIR}/envs/ipad.env"
    ;;
    projector)
        stack_files=("${APPS_DIR}/docker-compose-projector.yaml")
        env_file="${ROOT_DIR}/envs/projector.env"
    ;;
    user)
        stack_files=("${APPS_DIR}/docker-compose-user.yaml")
        env_file="${ROOT_DIR}/envs/user.env"
    ;;
    timeline-player)
        stack_files=("${APPS_DIR}/docker-compose-timeline-player.yaml")
        env_file="${ROOT_DIR}/envs/timeline-player.env"
    ;;
    all)
        stack_files=("${APPS_DIR}/docker-compose-all.yaml")
        env_file="${ROOT_DIR}/envs/all.env"
    ;;
    *)
        echo "Unknown stack: ${stack}" >&2
        exit 1
    ;;
esac

ensure_domain_env_consistency "${stack}" "${env_file}"

should_ensure_domain_bridge=false
case "${stack}" in
    perception|speech|all)
        if [[ "${HARU_COMPOSE_AUTO_DOMAIN_BRIDGE:-true}" != "false" && "${HARU_COMPOSE_AUTO_DOMAIN_BRIDGE:-true}" != "0" ]]; then
            for arg in "$@"; do
                if [[ "${arg}" == "up" || "${arg}" == "start" ]]; then
                    should_ensure_domain_bridge=true
                    break
                fi
            done
        fi
    ;;
esac

if [[ "${should_ensure_domain_bridge}" == "true" ]]; then
    domain_bridge_env_args=()
    if [[ -f "${ROBOT_ENV_FILE}" ]]; then
        domain_bridge_env_args+=(--env-file "${ROBOT_ENV_FILE}")
    fi
    domain_bridge_env_args+=(--env-file "${ROOT_DIR}/envs/domain-bridge.env")

    docker compose \
        -f "${APPS_DIR}/docker-compose-domain-bridge.yaml" \
        "${domain_bridge_env_args[@]}" \
        up -d --force-recreate
fi

cmd=(docker compose)
for stack_file in "${stack_files[@]}"; do
    cmd+=(-f "${stack_file}")
done
if [[ -f "${ROBOT_ENV_FILE}" ]]; then
    cmd+=(--env-file "${ROBOT_ENV_FILE}")
fi
cmd+=(--env-file "${env_file}")

exec "${cmd[@]}" "$@"
