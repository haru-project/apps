#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${1:-${ROOT_DIR}/config/domain_bridge.yaml}"
IMAGE="${PERCEPTION_DOMAIN_BRIDGE_IMAGE:-ghcr.io/haru-project/haru-domain-bridge-jazzy:latest}"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "Domain bridge config not found: ${CONFIG_PATH}" >&2
  exit 1
fi

docker run --rm \
  -v "${CONFIG_PATH}:/config/domain_bridge.yaml:ro" \
  "${IMAGE}" \
  bash -lc '
    set -euo pipefail
    set +u
    source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash
    source /opt/ros/${ROS_DISTRO:-jazzy}/workspace/install/setup.bash
    set -u
    python3 - <<'"'"'PY'"'"' | sort -u | while IFS= read -r interface_type; do
import sys
import yaml

with open("/config/domain_bridge.yaml", "r", encoding="utf-8") as stream:
    config = yaml.safe_load(stream) or {}

for topic_name, topic_config in (config.get("topics") or {}).items():
    if not isinstance(topic_config, dict):
        continue
    interface_type = topic_config.get("type")
    if interface_type:
        print(interface_type)
PY
      echo "Checking ${interface_type}"
      ros2 interface show "${interface_type}" >/dev/null
    done
  '
