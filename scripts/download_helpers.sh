#!/usr/bin/env bash
set -euo pipefail
set -o pipefail

cleanup_data_dir() {
  local dir="$1"
  if [ -d "$dir" ]; then
    if ! rm -rf "$dir"; then
      echo "Unable to remove ${dir} (permission issue). Please remove it manually and rerun." >&2
      exit 1
    fi
  fi
  mkdir -p "$dir"
}

copy_with_tar() {
  local image="$1"
  local src="$2"
  local dest="$3"
  mkdir -p "$dest"
  docker run --rm --entrypoint tar "$image" -C "$src" -cf - . | tar xf - -C "$dest"
}
