#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="${ROOT_DIR}/apps"

stack="${1:-}"
if [[ -z "${stack}" ]]; then
    echo "Usage: $(basename "$0") <stack> <docker compose args...>" >&2
    echo "Stacks: perception | speech | llm | reasoner | tts | simulator | ipad | projector | user | recorder | all" >&2
    exit 1
fi
shift

stack_files=()

case "${stack}" in
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
    recorder)
        stack_files=("${APPS_DIR}/docker-compose-recorder.yaml")
        env_file="${ROOT_DIR}/envs/recorder.env"
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

cmd=(docker compose)
for stack_file in "${stack_files[@]}"; do
    cmd+=(-f "${stack_file}")
done
cmd+=(--env-file "${env_file}")

exec "${cmd[@]}" "$@"
