#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

dry_run="${DRY_RUN:-false}"

copy_tree() {
  local source="$1"
  local target="$2"

  if [[ ! -e "${source}" ]]; then
    printf '[haru-cache-migrate] skip missing %s\n' "${source}" >&2
    return 0
  fi

  printf '[haru-cache-migrate] %s -> %s\n' "${source}" "${target}" >&2
  if [[ "${dry_run}" == "true" ]]; then
    return 0
  fi

  mkdir -p "${target}"
  cp -an "${source}/." "${target}/"
}

copy_tree \
  "${HOME}/.ros/strawberry_ros_skeletons/models" \
  "${HOME}/haru-perception-cache/skeletons/models"

copy_tree \
  "${HOME}/.ros/strawberry_ros_faces_module/cache" \
  "${ROOT_DIR}/data/perception/cache"

copy_tree \
  "${HOME}/.ros/strawberry_ros_faces_module/faces_recognitor" \
  "${ROOT_DIR}/data/perception/faces_recognitor"

printf '[haru-cache-migrate] done\n' >&2
