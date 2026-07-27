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

mkdir -p \
  "${HOME}/.ros/haru_speech" \
  "${HOME}/haru-speech-cache/models" \
  "${HOME}/haru-speech-cache/voices" \
  "${HOME}/haru-perception-cache/skeletons/models" \
  "${HOME}/.cache/huggingface" \
  "${HOME}/.local/share/haru_viz/recordings"

if ! docker pull "${CONFIGURATOR_IMAGE}" >/dev/null 2>&1; then
  if ! docker image inspect "${CONFIGURATOR_IMAGE}" >/dev/null 2>&1; then
    echo "Published configurator is unavailable; building the matching local image." >&2
    docker build -t "${LOCAL_IMAGE}" -f "${ROOT_DIR}/configurator/Dockerfile" "${ROOT_DIR}/configurator"
    CONFIGURATOR_IMAGE="${LOCAL_IMAGE}"
  else
    echo "Registry pull failed; using the cached configurator image." >&2
  fi
fi

repo_schema="$(tr -d '[:space:]' < "${ROOT_DIR}/configurator/schema-version")"
image_schema="$(
  docker image inspect "${CONFIGURATOR_IMAGE}" \
    --format '{{range .Config.Env}}{{println .}}{{end}}' |
    sed -n 's/^HARU_CONFIGURATOR_SCHEMA_VERSION=//p' |
    tail -1
)"
if [[ "${image_schema}" != "${repo_schema}" ]]; then
  echo "Published configurator schema ${image_schema:-unknown} does not match repository schema ${repo_schema}; building locally." >&2
  docker build -t "${LOCAL_IMAGE}" -f "${ROOT_DIR}/configurator/Dockerfile" "${ROOT_DIR}/configurator"
  CONFIGURATOR_IMAGE="${LOCAL_IMAGE}"
fi

socket_gid="$(stat -c '%g' /var/run/docker.sock)"
run_args=(
  --rm
  --network host
  --user "$(id -u):$(id -g)"
  --group-add "${socket_gid}"
  -e "HOME=/tmp/haru-home"
  -e "HARU_REPO_ROOT=${ROOT_DIR}"
  -e "HARU_HOST_HOME=${HOME}"
  -e "HARU_HOST_UID=$(id -u)"
  -e "HARU_HOST_GID=$(id -g)"
  -e "HARU_HOST_XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
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
  audio_gid="$(stat -c '%g' /dev/snd)"
  run_args+=(--group-add "${audio_gid}")
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
