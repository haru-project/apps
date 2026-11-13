#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER="${DIR}/../data/memory"

source "${DIR}/download_helpers.sh"

MEMORY_COMPOSE_FILE="${DIR}/../apps/docker-compose-memory.yaml"
MEMORY_ENV_FILE="${DIR}/../envs/memory.env"
IMAGE_TAG="$(compose_service_image "${MEMORY_COMPOSE_FILE}" "${MEMORY_ENV_FILE}" agent-memory)"
WEAVIATE_HOST="$(compose_service_environment "${MEMORY_COMPOSE_FILE}" "${MEMORY_ENV_FILE}" agent-memory WEAVIATE_HOST)"
WEAVIATE_PORT="$(compose_service_environment "${MEMORY_COMPOSE_FILE}" "${MEMORY_ENV_FILE}" agent-memory WEAVIATE_PORT)"
WEAVIATE_GRPC_PORT="$(compose_service_environment "${MEMORY_COMPOSE_FILE}" "${MEMORY_ENV_FILE}" agent-memory WEAVIATE_GRPC_PORT)"

cleanup_data_dir "${DATA_FOLDER}"
copy_with_tar "${IMAGE_TAG}" \
  /ws/install/agent_memory/share/agent_memory/config \
  "${DATA_FOLDER}/configs"

python3 "${DIR}/configure_memory_data.py" \
  "${DATA_FOLDER}/configs/agent_memory.yaml" \
  "${WEAVIATE_HOST}" \
  "${WEAVIATE_PORT}" \
  "${WEAVIATE_GRPC_PORT}"

chmod -R a+rwX "${DATA_FOLDER}"
