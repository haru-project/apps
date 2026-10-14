#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

# Collect images once per stack, preserving a stable order and deduplicating repeats.
declare -a image_list=()
declare -A seen_images=()

for stack in "${requested_stacks[@]}"; do
    echo "Resolving images for ${stack}..."
    # Enable the `all` profile and the stack-specific profile (if any).
    profiles_args=(--profile all)
    if [[ "${stack}" == "timeline-player" ]]; then
        profiles_args+=(--profile timeline-compat)
    elif [[ "${stack}" == "speech" ]]; then
        # Include the optional base service when downloading the full speech stack.
        profiles_args+=(--profile speech --profile monolithic)
    elif [[ "${stack}" != "all" ]]; then
        profiles_args+=(--profile "${stack}")
    fi

    images="$(bash "${ROOT_DIR}/scripts/compose.sh" "$stack" "${profiles_args[@]}" config --images)"
    while IFS= read -r image; do
        [[ -z "${image}" ]] && continue
        [[ "${image}" == "scratch" ]] && continue
        if [[ -z "${seen_images[$image]+x}" ]]; then
            seen_images["$image"]=1
            image_list+=("$image")
        fi
    done <<< "$images"
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
