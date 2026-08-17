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
#
# Output is nvidia-smi's own CSV, so fields carry a leading space after each comma
# (read it with skipinitialspace=True, or equivalent).
set -euo pipefail
out="${1:-gpu-apps.csv}"
interval="${2:-1}"
mkdir -p "$(dirname "${out}")"
echo "timestamp_utc,pid,process_name,used_memory_mib" > "${out}"

# TZ=UTC because nvidia-smi stamps LOCAL time with no offset marker. Every other artifact here
# is Unix-epoch (ROS bags, LLM spans, redis), so a local-time column would silently misalign
# this file by the host's UTC offset when the timelines are joined.
export TZ=UTC

# One long-lived nvidia-smi doing its own polling: no per-sample process spawns, one open file.
# This samples the host it is measuring, so a shell loop respawning date/nvidia-smi twice a
# second would be load the profiled system does not otherwise carry. Per-process GPU memory
# moves on model-load timescales, so 1 s is ample.
exec nvidia-smi --query-compute-apps=timestamp,pid,process_name,used_memory \
  --format=csv,noheader,nounits -l "${interval}" >> "${out}"
