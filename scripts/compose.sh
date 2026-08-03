#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="${ROOT_DIR}/apps"
local_env_file="${ROOT_DIR}/.haru/local.env"
use_local_config=true
case "${HARU_COMPOSE_IGNORE_LOCAL_CONFIG:-false}" in
    1|true|TRUE|True|yes|YES|Yes|on|ON|On) use_local_config=false ;;
esac

stack="${1:-}"
if [[ -z "${stack}" ]]; then
    echo "Usage: $(basename "$0") <stack> <docker compose args...>" >&2
    echo "Stacks: domain-bridge | perception | speech | llm | reasoner | tts | simulator | ipad | projector | user | nlp | timeline-player | memory | all" >&2
    exit 1
fi
shift

stack_files=()
nlp_profile="cpu"
deployment_profile="${HARU_DEPLOYMENT:-}"
nlp_gpu_enabled="${HARU_NLP_SERVER_GPU_ENABLED:-}"
if [[ "${use_local_config}" == "true" && -f "${local_env_file}" ]]; then
    while IFS='=' read -r key value; do
        case "${key}" in
            HARU_DEPLOYMENT)
                if [[ -z "${deployment_profile}" ]]; then
                    deployment_profile="${value}"
                fi
            ;;
            HARU_NLP_SERVER_GPU_ENABLED)
                if [[ -z "${nlp_gpu_enabled}" ]]; then
                    nlp_gpu_enabled="${value}"
                fi
            ;;
        esac
    done < "${local_env_file}"
fi
case "${deployment_profile:-physical}" in
    physical|simulator) ;;
    *)
        echo "HARU_DEPLOYMENT must be physical or simulator." >&2
        exit 1
    ;;
esac
case "${nlp_gpu_enabled:-false}" in
    1|true|TRUE|True|yes|YES|Yes|on|ON|On)
        nlp_profile="gpu"
    ;;
    0|false|FALSE|False|no|NO|No|off|OFF|Off|"")
        nlp_profile="cpu"
    ;;
    *)
        echo "HARU_NLP_SERVER_GPU_ENABLED must be true or false." >&2
        exit 1
    ;;
esac

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
    nlp)
        stack_files=("${APPS_DIR}/docker-compose-nlp.yaml")
        env_file="${ROOT_DIR}/envs/nlp-${nlp_profile}.env"
    ;;
    timeline-player)
        stack_files=("${APPS_DIR}/docker-compose-timeline-player.yaml")
        env_file="${ROOT_DIR}/envs/timeline-player.env"
    ;;
    memory)
        stack_files=("${APPS_DIR}/docker-compose-memory.yaml")
        env_file="${ROOT_DIR}/envs/memory.env"
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

should_ensure_domain_bridge=false
case "${stack}" in
    perception|speech)
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
    docker compose \
        -f "${APPS_DIR}/docker-compose-domain-bridge.yaml" \
        --env-file "${ROOT_DIR}/envs/domain-bridge.env" \
        up -d --force-recreate
fi

cmd=(docker compose)
for stack_file in "${stack_files[@]}"; do
    cmd+=(-f "${stack_file}")
done
cmd+=(--env-file "${env_file}")
if [[ "${stack}" == "nlp" || "${stack}" == "all" ]]; then
    cmd+=(--profile "${nlp_profile}")
fi
if [[ "${stack}" == "timeline-player" ]]; then
    cmd+=(--profile timeline-compat)
fi
if [[ "${stack}" == "all" ]]; then
    cmd+=(--profile all --profile "${deployment_profile:-physical}")
fi

local_override_file="${ROOT_DIR}/.haru/compose-${stack}.yaml"
if [[ "${use_local_config}" == "true" && -f "${local_env_file}" ]]; then
    cmd+=(--env-file "${local_env_file}")
fi
if [[ "${use_local_config}" == "true" && -f "${local_override_file}" ]]; then
    cmd+=(-f "${local_override_file}")
fi

exec "${cmd[@]}" "$@"
