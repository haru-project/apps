#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="${ROOT_DIR}/apps"

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=true
    shift
fi

requested_stacks=("$@")
if [[ ${#requested_stacks[@]} -eq 0 ]]; then
    requested_stacks=(
        domain-bridge
        perception
        speech
        llm
        reasoner
        tts
        simulator
        ipad
        projector
        user
        timeline-player
        memory
        all
    )
fi

declare -A COMPOSE_FILES=(
    [domain-bridge]="${APPS_DIR}/docker-compose-domain-bridge.yaml"
    [perception]="${APPS_DIR}/docker-compose-perception.yaml"
    [speech]="${APPS_DIR}/docker-compose-speech.yaml"
    [llm]="${APPS_DIR}/docker-compose-llm.yaml"
    [reasoner]="${APPS_DIR}/docker-compose-reasoner.yaml"
    [tts]="${APPS_DIR}/docker-compose-tts.yaml"
    [simulator]="${APPS_DIR}/docker-compose-simulator.yaml"
    [ipad]="${APPS_DIR}/docker-compose-ipad.yaml"
    [projector]="${APPS_DIR}/docker-compose-projector.yaml"
    [user]="${APPS_DIR}/docker-compose-user.yaml"
    [timeline-player]="${APPS_DIR}/docker-compose-timeline-player.yaml"
    [memory]="${APPS_DIR}/docker-compose-memory.yaml"
    [all]="${APPS_DIR}/docker-compose-all.yaml"
)

declare -A ENV_FILES=(
    [domain-bridge]="${ROOT_DIR}/envs/domain-bridge.env"
    [perception]="${ROOT_DIR}/envs/perception.env"
    [speech]="${ROOT_DIR}/envs/speech.env"
    [llm]="${ROOT_DIR}/envs/llm.env"
    [reasoner]="${ROOT_DIR}/envs/reasoner.env"
    [tts]="${ROOT_DIR}/envs/tts.env"
    [simulator]="${ROOT_DIR}/envs/simulator.env"
    [ipad]="${ROOT_DIR}/envs/ipad.env"
    [projector]="${ROOT_DIR}/envs/projector.env"
    [user]="${ROOT_DIR}/envs/user.env"
    [timeline-player]="${ROOT_DIR}/envs/timeline-player.env"
    [memory]="${ROOT_DIR}/envs/memory.env"
    [all]="${ROOT_DIR}/envs/all.env"
)

for stack in "${requested_stacks[@]}"; do
    if [[ -z "${COMPOSE_FILES[$stack]+x}" ]]; then
        echo "Unknown stack: ${stack}" >&2
        exit 1
    fi
done

# Collect images once per stack, preserving a stable order and deduplicating repeats.
declare -a image_list=()
declare -A seen_images=()

for stack in "${requested_stacks[@]}"; do
    compose_file="${COMPOSE_FILES[$stack]}"
    env_file="${ENV_FILES[$stack]}"

    echo "Resolving images for ${stack}..."
    # Enable the `all` profile and the stack-specific profile (if any).
    profiles_args=(--profile all)
    if [[ "${stack}" == "timeline-player" ]]; then
        profiles_args+=(--profile timeline-compat)
    elif [[ "${stack}" != "all" ]]; then
        profiles_args+=(--profile "${stack}")
    fi

    while IFS= read -r image; do
        [[ -z "${image}" ]] && continue
        [[ "${image}" == "scratch" ]] && continue
        if [[ -z "${seen_images[$image]+x}" ]]; then
            seen_images["$image"]=1
            image_list+=("$image")
        fi
    done < <(docker compose -f "${compose_file}" --env-file "${env_file}" "${profiles_args[@]}" config --images 2>/dev/null || true)
done

if [[ ${#image_list[@]} -eq 0 ]]; then
    echo "No images found." >&2
    exit 1
fi

echo
if [[ "${dry_run}" == "true" ]]; then
    echo "Dry run: the following images would be pulled:"
else
    echo "Pulling ${#image_list[@]} images..."
fi

for image in "${image_list[@]}"; do
    if [[ "${dry_run}" == "true" ]]; then
        echo "  ${image}"
    else
        echo "Pulling ${image}"
        docker pull "${image}"
    fi
done

echo
if [[ "${dry_run}" == "true" ]]; then
    echo "Dry run complete."
else
    echo "All requested images were pulled successfully."
fi
