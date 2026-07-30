#!/usr/bin/env bash
set -euo pipefail

REGISTRY="ghcr.io"
CHECK_IMAGE="${HARU_REGISTRY_CHECK_IMAGE:-${STRAWBERRY_TTS_API_IMAGE:-ghcr.io/haru-project/strawberry-tts-api:v0.3.1-5090}}"

registry_access_works() {
  docker manifest inspect "${CHECK_IMAGE}" >/dev/null 2>&1
}

login_with_gh() {
  local github_user token_file
  token_file="${HARU_GITHUB_TOKEN_FILE:-}"
  github_user="${HARU_GITHUB_USER:-}"
  if [[ -n "${token_file}" && -r "${token_file}" && -n "${github_user}" ]]; then
    echo "Existing Docker credentials cannot access Haru images; trying the authenticated GitHub CLI account ${github_user}." >&2
    docker login "${REGISTRY}" --username "${github_user}" --password-stdin \
      < "${token_file}" >/dev/null
    return
  fi

  command -v gh >/dev/null 2>&1 || return 1
  github_user="$(gh api user --jq .login 2>/dev/null)" || return 1
  [[ -n "${github_user}" ]] || return 1

  echo "Existing Docker credentials cannot access Haru images; trying the authenticated GitHub CLI account ${github_user}." >&2
  gh auth token --hostname github.com 2>/dev/null |
    docker login "${REGISTRY}" --username "${github_user}" --password-stdin >/dev/null
}

login_interactively() {
  [[ -t 0 && -t 1 ]] || return 1

  local github_user github_token
  echo "Authentication is required to pull Haru's private images from ${REGISTRY}." >&2
  if ! read -r -p "GitHub username: " github_user; then
    return 1
  fi
  if ! read -r -s -p "GitHub token with read:packages access: " github_token; then
    echo >&2
    return 1
  fi
  echo >&2
  [[ -n "${github_user}" && -n "${github_token}" ]] || return 1

  if ! printf '%s' "${github_token}" |
    docker login "${REGISTRY}" --username "${github_user}" --password-stdin >/dev/null; then
    unset github_token
    return 1
  fi
  unset github_token
}

if registry_access_works; then
  exit 0
fi

if login_with_gh && registry_access_works; then
  echo "Authenticated to ${REGISTRY} using the GitHub CLI account." >&2
  exit 0
fi

if login_interactively && registry_access_works; then
  echo "Authenticated to ${REGISTRY}." >&2
  exit 0
fi

cat >&2 <<EOF
Unable to access the private Haru image:
  ${CHECK_IMAGE}

Authenticate a GitHub account with access to haru-project packages, then retry:
  gh auth login --hostname github.com
  gh auth refresh --hostname github.com --scopes read:packages

Alternatively, create a token with read:packages access and run:
  printf '%s' "\${GITHUB_TOKEN}" | docker login ${REGISTRY} --username YOUR_GITHUB_USERNAME --password-stdin
EOF
exit 1
