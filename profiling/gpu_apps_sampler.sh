#!/usr/bin/env bash
# Host-side per-PID GPU memory sampler for per-SERVICE co-tenancy attribution.
#
# WHY host-side: running nvidia-smi --query-compute-apps INSIDE a container (under
# rootless docker + CDI) returns NOTHING — it can't enumerate GPU processes owned by
# other containers. Run THIS on the host (outside any container) and it sees every
# process on the card (LLM serve / TTS / speech), giving the per-service MEMORY split
# over one wall clock. record_session.sh launches it in the background.
#
# NOTE on per-service SM-UTIL (compute, not memory): real-time per-process SM occupancy
# on a shared GPU is NOT available without MPS/MIG partitioning — a hardware limit, not a
# tooling gap. Per-PID MEMORY (here) + a whole-card util timeline are the available
# attribution.
#
# Usage: bash gpu_apps_sampler.sh [out_csv] [interval_s]
set -uo pipefail
OUT="${1:-gpu-apps.csv}"
INT="${2:-0.5}"
mkdir -p "$(dirname "${OUT}")"
echo "timestamp,pid,process_name,used_memory_mib" > "${OUT}"
trap 'exit 0' TERM INT
while true; do
  ts="$(date -u +%Y-%m-%dT%H:%M:%S.%2N)"
  nvidia-smi --query-compute-apps=pid,process_name,used_memory \
    --format=csv,noheader,nounits 2>/dev/null \
    | while IFS=',' read -r pid name mem; do
        printf '%s,%s,%s,%s\n' "${ts}" "$(echo "${pid}" | xargs)" "$(echo "${name}" | xargs)" "$(echo "${mem}" | xargs)"
      done >> "${OUT}"
  sleep "${INT}"
done
