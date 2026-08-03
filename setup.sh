#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGURATOR_IMAGE="${HARU_CONFIGURATOR_IMAGE:-ghcr.io/haru-project/apps-configurator:demo-jiyugaoka}"
LOCAL_IMAGE="haru-apps-configurator:local"

has_arg() {
  local expected="$1"
  shift
  local argument
  for argument in "$@"; do
    [[ "${argument}" == "${expected}" ]] && return 0
  done
  return 1
}

image_schema() {
  docker image inspect "$1" \
    --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null |
    sed -n 's/^HARU_CONFIGURATOR_SCHEMA_VERSION=//p' |
    tail -1
}

if [[ ! -S /var/run/docker.sock ]]; then
  echo "Docker socket /var/run/docker.sock is unavailable." >&2
  exit 1
fi

requested_command="${1:-setup}"
if [[ ! -t 0 && "${requested_command}" == "setup" ]] && ! has_arg --answers "$@"; then
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

repo_schema="$(tr -d '[:space:]' < "${ROOT_DIR}/configurator/schema-version")"
if ! docker pull "${CONFIGURATOR_IMAGE}" >/dev/null 2>&1; then
  if ! docker image inspect "${CONFIGURATOR_IMAGE}" >/dev/null 2>&1; then
    if docker image inspect "${LOCAL_IMAGE}" >/dev/null 2>&1 \
      && [[ "$(image_schema "${LOCAL_IMAGE}")" == "${repo_schema}" ]]; then
      echo "Published configurator is unavailable; using the matching local image." >&2
      CONFIGURATOR_IMAGE="${LOCAL_IMAGE}"
    else
      echo "Published configurator is unavailable; building the matching local image." >&2
      docker build -t "${LOCAL_IMAGE}" -f "${ROOT_DIR}/configurator/Dockerfile" "${ROOT_DIR}/configurator"
      CONFIGURATOR_IMAGE="${LOCAL_IMAGE}"
    fi
  else
    echo "Registry pull failed; using the cached configurator image." >&2
  fi
fi

selected_image_schema="$(image_schema "${CONFIGURATOR_IMAGE}")"
if [[ "${selected_image_schema}" != "${repo_schema}" ]]; then
  echo "Published configurator schema ${selected_image_schema:-unknown} does not match repository schema ${repo_schema}; building locally." >&2
  docker build -t "${LOCAL_IMAGE}" -f "${ROOT_DIR}/configurator/Dockerfile" "${ROOT_DIR}/configurator"
  CONFIGURATOR_IMAGE="${LOCAL_IMAGE}"
fi

socket_gid="$(stat -c '%g' /var/run/docker.sock)"
runtime_docker_dir=""
cleanup_runtime_auth() {
  [[ -n "${runtime_docker_dir}" ]] || return 0
  rm -f -- \
    "${runtime_docker_dir}/config.json" \
    "${runtime_docker_dir}/github-token"
  if ! rmdir -- "${runtime_docker_dir}" 2>/dev/null; then
    echo "Warning: temporary Docker authentication directory was not empty: ${runtime_docker_dir}" >&2
  fi
}
trap cleanup_runtime_auth EXIT

github_user=""
needs_registry_auth=false
if [[ "${requested_command}" == "up" ]] \
  || { [[ "${requested_command}" == "setup" ]] && ! has_arg --dry-run "$@"; }; then
  needs_registry_auth=true
  runtime_parent="${XDG_RUNTIME_DIR:-/tmp}"
  runtime_docker_dir="$(mktemp -d "${runtime_parent}/haru-configurator-docker.XXXXXX")"
  host_docker_config="${DOCKER_CONFIG:-${HOME}/.docker}/config.json"
  python3 "${ROOT_DIR}/scripts/prepare_docker_auth.py" \
    "${host_docker_config}" "${runtime_docker_dir}/config.json"

  if command -v gh >/dev/null 2>&1; then
    github_user="$(gh api user --jq .login 2>/dev/null || true)"
    if [[ -n "${github_user}" ]] && gh auth token --hostname github.com \
      > "${runtime_docker_dir}/github-token" 2>/dev/null; then
      chmod 600 "${runtime_docker_dir}/github-token"
    else
      github_user=""
      rm -f -- "${runtime_docker_dir}/github-token"
    fi
  fi
fi

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
  -e "HARU_REPO_REVISION=$(git -C "${ROOT_DIR}" rev-parse HEAD)"
  -e "HARU_HOST_XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  -e "DISPLAY=${DISPLAY:-}"
  -e "XAUTHORITY=${XAUTHORITY:-}"
  -v "/var/run/docker.sock:/var/run/docker.sock"
  -v "${ROOT_DIR}:${ROOT_DIR}"
  -v "/sys:/host/sys:ro"
  -w "${ROOT_DIR}"
)
if [[ "${needs_registry_auth}" == true ]]; then
  run_args+=(
    -e "HARU_GITHUB_USER=${github_user}"
    -e "HARU_GITHUB_TOKEN_FILE=/tmp/haru-home/.docker/github-token"
    -v "${runtime_docker_dir}:/tmp/haru-home/.docker"
  )
fi

# Alpine containers do not use the host's NSS modules, so `.local` names that
# resolve through systemd-resolved on the host may be invisible inside the
# configurator. Resolve bounded robot names on the host for interactive setup,
# then seed discovery and the container's hosts file with those results.
if [[ "${requested_command}" == "setup" ]] && ! has_arg --answers "$@"; then
  discovered_robots=()
  while IFS=$'\t' read -r robot_host robot_address; do
    [[ -n "${robot_host}" && -n "${robot_address}" ]] || continue
    discovered_robots+=("${robot_host}")
    run_args+=(--add-host "${robot_host}:${robot_address}")
  done < <(python3 "${ROOT_DIR}/scripts/discover_robot_hosts.py" 2>/dev/null || true)
  if [[ "${#discovered_robots[@]}" -gt 0 ]]; then
    discovered_csv="$(IFS=,; echo "${discovered_robots[*]}")"
    run_args+=(-e "HARU_DISCOVERED_ROBOTS=${discovered_csv}")
  fi
fi

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

docker run "${run_args[@]}" "${CONFIGURATOR_IMAGE}" "$@"
