#!/usr/bin/env bash
# Usage: bash profiling/record_session.sh <label>          (run from the repo root)
#
# Records one live session read-only: two ROS-bag recorders (robot domain + perception domain,
# because a single-domain recorder misses the other half), serve-identity provenance, the
# goal-eval redis stream, and per-service GPU memory. Everything is keyed by <label> and stops
# together on Ctrl-C. Nothing is published into the ROS graph and no pipeline config changes.
#
# Domains default to this repo's HARU_ROBOT_ROS_DOMAIN_ID / HARU_PERCEPTION_ROS_DOMAIN_ID.
# Per-agent LLM spans are captured separately by a litellm callback — see profiling/README.md.
set -euo pipefail

label="${1:?usage: record_session.sh <label>}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Domains come from the repo's own variables (envs/all.env, start.sh), so a stack started with
# e.g. HARU_ROBOT_ROS_DOMAIN_ID=26 is recorded correctly instead of yielding empty bags.
robot_domain="${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}}"
perception_domain="${HARU_PERCEPTION_ROS_DOMAIN_ID:-200}"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "error: ros2 not found — source a ROS 2 environment, or run this inside a ROS container" >&2
  echo "       (see Prerequisites in profiling/README.md)" >&2
  exit 1
fi

out_dir="${script_dir}/out/${label}"
mkdir -p "${out_dir}" || { echo "cannot mkdir ${out_dir}" >&2; exit 1; }

pids=()

# --- one recorder per domain: robot side + perception/speech.
#     A single-domain recorder silently misses the other half of the session. ---
record_domain() {  # <domain> <name> <topic_file>
  local domain="$1" name="$2" topic_file="$3" topics=()
  # tr -d '\r': a CRLF-saved topic file would otherwise yield names with a trailing carriage
  # return, which subscribe to nothing and produce an EMPTY bag with no error.
  mapfile -t topics < <(grep -vE '^\s*#|^\s*$' "${topic_file}" | tr -d '\r')
  if [[ ${#topics[@]} -eq 0 ]]; then
    echo "error: no topics parsed from ${topic_file}" >&2
    exit 1
  fi
  ( export ROS_DOMAIN_ID="${domain}"
    exec ros2 bag record --storage mcap \
      -o "${out_dir}/${label}_${name}_d${domain}" "${topics[@]}" ) &
  pids+=($!)
}

record_domain "${robot_domain}" robot "${script_dir}/topics_robot.txt"
record_domain "${perception_domain}" perception "${script_dir}/topics_perception.txt"

# --- serve-identity provenance (HTTP, not a ROS topic). Backgrounded: it can wait on network
#     timeouts, and blocking here would drop the session's opening turns. ---
if [[ -n "${LLM_ENDPOINT:-}" ]]; then
  ( "${script_dir}/capture_serve_provenance.py" --label "${label}" \
      --out "${out_dir}/provenance.json" --endpoint "${LLM_ENDPOINT}" \
      || echo "warn: serve provenance capture failed (endpoint unreachable?)" >&2 ) &
  pids+=($!)
else
  echo "warn: LLM_ENDPOINT unset — skipping serve provenance (set it to the serve URL to capture)" >&2
fi

# --- goal-eval / TIMEDOUT redis sidecar (the proxy is pipeline-computed post-LLM, so it lives
#     on redis, not the litellm stream) ---
"${script_dir}/redis_goaleval_logger.py" "${label}" "${out_dir}/goal_eval.jsonl" \
  --host "${REDIS_HOST:-127.0.0.1}" --port "${REDIS_PORT:-6379}" \
  --channel "${REDIS_CHANNEL:-haru_llm_dashboard}" &
pids+=($!)

# --- per-service GPU memory sampler (host-side; see the header in gpu_apps_sampler.sh) ---
if command -v nvidia-smi >/dev/null 2>&1; then
  bash "${script_dir}/gpu_apps_sampler.sh" "${out_dir}/gpu_${label}.csv" \
    "${HARU_PROFILING_GPU_INTERVAL:-1}" &
  pids+=($!)
else
  echo "warn: nvidia-smi not found on this host — GPU sampler skipped" >&2
fi

echo "profiling session '${label}' (robot domain ${robot_domain}, perception ${perception_domain})" >&2
echo "stop with Ctrl-C (or: kill -INT ${pids[*]})" >&2
trap 'kill -INT "${pids[@]}" 2>/dev/null || true' INT TERM EXIT
# `|| true`: on Ctrl-C the interrupted children make wait non-zero, and under `set -e` that
# would exit before the trap stops the remaining sidecars.
wait "${pids[@]}" || true
