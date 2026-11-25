#!/bin/bash


set -u
set -o pipefail

declare -A ACTIVE_PIDS=()

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOG_ROOT="${SCRIPT_DIR}/../data/docker_logs"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${LOG_ROOT}/${RUN_ID}"
mkdir -p "$LOG_DIR"


declare -A ALLOWED_CONTAINERS=(
    [haru-domain-bridge-domain-bridge-1]=1
    [haru-tts-cerevoice-api-1]=1
    [haru-tts-gpt-sovits-1]=1
    [haru-tts-tts-client-1]=1
    [haru-tts-ros-node-1]=1
    [haru-perception-azure-kinect-1]=1
    [haru-perception-faces-1]=1
    [haru-perception-skeletons-1]=1
    [haru-perception-belief-1]=1
    [haru-perception-viz-1]=1
    [haru-speech-verification-1]=1
    [haru-speech-localization-1]=1
    [haru-speech-audio-1]=1
    [haru-speech-recognition-1]=1
    [haru-timeline-player-timeline-player-1]=1
    [haru-llm-redis-1]=1
    [haru-llm-server-1]=1
    [haru-llm-dashboard-1]=1
    [haru-llm-action-args-1]=1
    [agent-memory-agent-memory-t2v-1]=1
    [agent-memory-agent-memory-weaviate-1]=1
    [agent-memory-agent-memory-1]=1
    [haru-reasoner-bt-forest-1]=1
    [haru-reasoner-context-manager-1]=1
    [haru-reasoner-reasoner-1]=1
    [haru-reasoner-execute-task-scenario-1]=1
)

# This script harvests logs from the allowed Docker containers only
# and continues to monitor for new allowed containers that start,
# saving their logs to a timestamped directory under $LOG_ROOT.

echo "Starting docker logs harvester. Saving to $LOG_DIR..."

cleanup() {
    local container_name
    for container_name in "${!ACTIVE_PIDS[@]}"; do
        if kill -0 "${ACTIVE_PIDS[$container_name]}" 2>/dev/null; then
            echo "Stopping log follower for $container_name"
            kill "${ACTIVE_PIDS[$container_name]}" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM EXIT

track_container() {
    local container_name="$1"
    local log_file="${LOG_DIR}/${container_name}.log"

    if [[ -n "${ACTIVE_PIDS[$container_name]:-}" ]] && kill -0 "${ACTIVE_PIDS[$container_name]}" 2>/dev/null; then
        return 0
    fi

    echo "Tracking container: $container_name"
    docker logs -f "$container_name" >> "$log_file" 2>&1 &
    ACTIVE_PIDS["$container_name"]=$!
}

should_track_container() {
    local container_name="$1"
    [[ -n "${ALLOWED_CONTAINERS[$container_name]:-}" ]]
}

# 1. Harvest logs from containers that are already running.
while IFS= read -r container_name; do
    [ -n "$container_name" ] || continue
    if ! should_track_container "$container_name"; then
        continue
    fi
    track_container "$container_name"
done < <(docker ps --format '{{.Names}}')

# 2. Subscribe to Docker events to capture new allowed containers as they start.
while IFS= read -r container_name; do
    [ -n "$container_name" ] || continue
    if ! should_track_container "$container_name"; then
        continue
    fi
    echo "New container detected: $container_name. Starting stream..."
    track_container "$container_name"
done < <(docker events --filter 'event=start' --filter 'type=container' --format '{{.Actor.Attributes.name}}')