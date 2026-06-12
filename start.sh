#!/usr/bin/env bash
set -euo pipefail

# Prevent double-starting stacks on the same host.
require_stack_down() {
  local stack="$1"
  if [[ -n "$(bash scripts/compose.sh "${stack}" ps -q)" ]]; then
    echo "Stack '${stack}' already has running containers. Stop it first (./stop.sh) or run compose down." >&2
    exit 1
  fi
}

# Ensure GUI services target the remote host display by default.
# Allow overrides from the environment if explicitly set.
if [[ -z "${XAUTHORITY:-}" ]]; then
  if [[ -r /run/user/1000/gdm/Xauthority ]]; then
    export XAUTHORITY="/run/user/1000/gdm/Xauthority"
  else
    export XAUTHORITY="${HOME}/.Xauthority"
  fi
fi
if [[ -z "${DISPLAY:-}" ]]; then
  for socket in /tmp/.X11-unix/X*; do
    [[ -S "${socket}" ]] || continue
    display=":${socket##*/X}"
    if command -v xset >/dev/null 2>&1; then
      if DISPLAY="${display}" XAUTHORITY="${XAUTHORITY}" xset -q >/dev/null 2>&1; then
        export DISPLAY="${display}"
        break
      fi
    fi
  done
  if [[ -z "${DISPLAY:-}" ]]; then
    # Fallback to :0 or :1 if xset is unavailable.
    if [[ -S /tmp/.X11-unix/X0 ]]; then
      export DISPLAY=":0"
    elif [[ -S /tmp/.X11-unix/X1 ]]; then
      export DISPLAY=":1"
    fi
  fi
fi
if [[ -z "${DISPLAY:-}" ]]; then
  echo "Warning: DISPLAY is not set and no usable X socket found. GUI windows will not appear." >&2
else
  if command -v xhost >/dev/null 2>&1; then
    DISPLAY="${DISPLAY}" XAUTHORITY="${XAUTHORITY}" xhost +si:localuser:root >/dev/null 2>&1 || true
  fi
fi

# Guard against already-running stacks.
require_stack_down tts
require_stack_down simulator
require_stack_down ipad
require_stack_down perception
require_stack_down speech
require_stack_down llm
require_stack_down reasoner
require_stack_down timeline-player

# Ipad services
# bash scripts/compose.sh ipad up server --force-recreate -d

# Projector services
# bash scripts/compose.sh simulator up unity-app web-server --force-recreate -d

# TTS services
bash scripts/compose.sh tts --profile tts up gpt-sovits cerevoice-api tts-client ros-node --force-recreate -d

# Perception services
HARU_COMPOSE_AUTO_DOMAIN_BRIDGE=true bash scripts/compose.sh perception up --force-recreate -d

# Speech services
HARU_COMPOSE_AUTO_DOMAIN_BRIDGE=true bash scripts/compose.sh speech up audio recognition verification localization --force-recreate -d

# Timeline Player services
bash scripts/compose.sh timeline-player up --force-recreate -d
# LLM services
bash scripts/compose.sh llm up action-args dashboard --force-recreate -d
# Reasoner services
bash scripts/compose.sh reasoner up bt-forest --force-recreate -d

