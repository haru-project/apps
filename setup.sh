#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGURATOR_IMAGE="${HARU_CONFIGURATOR_IMAGE:-ghcr.io/haru-project/apps-configurator:demo-jiyugaoka}"
LOCAL_IMAGE="haru-apps-configurator:local"

if [[ ! -S /var/run/docker.sock ]]; then
  echo "Docker socket /var/run/docker.sock is unavailable." >&2
  exit 1
fi

requested_command="${1:-setup}"
if [[ ! -t 0 && "${requested_command}" == "setup" && " $* " != *" --answers "* ]]; then
  echo "Interactive setup requires a TTY. Use --answers FILE for automation." >&2
  exit 1
fi

echo "Warning: the Haru configurator receives the Docker socket and can control this host." >&2

if ! docker pull "${CONFIGURATOR_IMAGE}" >/dev/null 2>&1; then
  if ! docker image inspect "${CONFIGURATOR_IMAGE}" >/dev/null 2>&1; then
    echo "Published configurator is unavailable; building the matching local image." >&2
    docker build -t "${LOCAL_IMAGE}" -f "${ROOT_DIR}/configurator/Dockerfile" "${ROOT_DIR}/configurator"
    CONFIGURATOR_IMAGE="${LOCAL_IMAGE}"
  else
    echo "Registry pull failed; using the cached configurator image." >&2
  fi
fi

socket_gid="$(stat -c '%g' /var/run/docker.sock)"
run_args=(
  --rm
  --network host
  --user "$(id -u):$(id -g)"
  --group-add "${socket_gid}"
  -e "HOME=/tmp/haru-home"
  -e "HARU_REPO_ROOT=${ROOT_DIR}"
  -e "DISPLAY=${DISPLAY:-}"
  -e "XAUTHORITY=${XAUTHORITY:-}"
  -v "/var/run/docker.sock:/var/run/docker.sock"
  -v "${ROOT_DIR}:${ROOT_DIR}"
  -v "/sys:/host/sys:ro"
  -w "${ROOT_DIR}"
)

if [[ -t 0 && -t 1 ]]; then
  run_args+=(-it)
fi
if [[ -d /dev/snd ]]; then
  run_args+=(-v "/dev/snd:/dev/snd")
fi
if [[ -d /run/udev ]]; then
  run_args+=(-v "/run/udev:/run/udev:ro")
fi
if [[ -d /tmp/.X11-unix ]]; then
  run_args+=(-v "/tmp/.X11-unix:/tmp/.X11-unix:rw")
fi
if [[ -n "${XAUTHORITY:-}" && -r "${XAUTHORITY}" ]]; then
  run_args+=(-v "${XAUTHORITY}:${XAUTHORITY}:ro")
fi

if [[ "$#" -eq 0 ]]; then
  set -- setup
fi

exec docker run "${run_args[@]}" "${CONFIGURATOR_IMAGE}" "$@"
