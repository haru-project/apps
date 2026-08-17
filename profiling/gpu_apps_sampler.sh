#!/usr/bin/env bash
# Per-PID GPU memory sampler — which service holds what on a shared card.
#
# Usage: bash gpu_apps_sampler.sh [out_csv] [interval_s]
#
# Run it on the HOST, not in a container: nvidia-smi inside a container cannot enumerate GPU
# processes owned by other containers and returns nothing useful.
#
# Memory only. Per-process SM utilisation is not available on a shared GPU without MPS/MIG.
#
# Output is nvidia-smi's own CSV, so fields carry a leading space after each comma.
set -euo pipefail
out="${1:-gpu-apps.csv}"
interval="${2:-1}"
mkdir -p "$(dirname "${out}")"
echo "timestamp_utc,pid,process_name,used_memory_mib" > "${out}"

# nvidia-smi stamps LOCAL time with no offset marker; every other artifact is Unix-epoch, so
# without this the column silently misaligns by the host's UTC offset when timelines are joined.
export TZ=UTC

# nvidia-smi does its own polling, so this samples the host it is measuring without respawning
# a process per sample. Per-process GPU memory moves on model-load timescales; 1 s is ample.
exec nvidia-smi --query-compute-apps=timestamp,pid,process_name,used_memory \
  --format=csv,noheader,nounits -l "${interval}" >> "${out}"
