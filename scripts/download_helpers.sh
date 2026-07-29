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

compose_service_image() {
  local compose_file="$1"
  local env_file="$2"
  local service="$3"
  docker compose -f "$compose_file" --env-file "$env_file" config --format json "$service" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["services"][sys.argv[1]]["image"])' "$service"
}

compose_service_environment() {
  local compose_file="$1"
  local env_file="$2"
  local service="$3"
  local variable="$4"
  docker compose -f "$compose_file" --env-file "$env_file" config --format json "$service" |
    python3 -c '
import json
import sys

service = json.load(sys.stdin)["services"][sys.argv[1]]
value = service.get("environment", {}).get(sys.argv[2])
if value is None:
    raise SystemExit(f"{sys.argv[2]} is not set for service {sys.argv[1]}")
print(value)
' "$service" "$variable"
}
