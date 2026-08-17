#!/usr/bin/env bash
# Usage: record_session.sh <label> [--reasoner-domain N] [--out-base DIR]
#
# Deployment profiling: capture one live session's turn anatomy as PASSIVE observers —
# nothing in the robot pipeline changes. Reconstructs the same breakpoints as the harness
# simulation waterfall (t0 = ASR result, per-agent LLM spans, TTFR = first TTS playing edge,
# turn anatomy) plus per-service GPU load, so demo sessions are directly comparable.
#
# Starts these sidecars, all keyed by <label>, and stops them together on Ctrl-C:
#   - two ROS-bag recorders: reasoner domain (default 0) + perception/speech domain 200
#     (a single-domain recorder misses the other)
#   - serve-identity provenance (capture_serve_provenance.py)
#   - goal-eval / TIMEDOUT redis sidecar (redis_goaleval_logger.py)
#   - per-service GPU memory sampler (gpu_apps_sampler.sh)
# Per-agent LLM spans are captured by the litellm callback (litellm_agent_spans.py) when the
# operator enables it — see profiling/README.md; not launched here.
set -uo pipefail

label="${1:?usage: record_session.sh <label> [--reasoner-domain N] [--out-base DIR]}"; shift || true
reasoner_domain=0
out_base=""
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reasoner-domain) reasoner_domain="${2:?}"; shift 2 ;;
    --out-base) out_base="${2:?}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
out_base="${out_base:-${script_dir}/out}"
out_dir="${out_base}/${label}"
mkdir -p "${out_dir}" || { echo "cannot mkdir ${out_dir}" >&2; exit 1; }
echo "${label}" > "${out_dir}/LABEL.txt"

# --- serve-identity provenance (not a ROS topic — HTTP). LLM_ENDPOINT must point at the serve
#     actually answering requests; a wrong endpoint pins the wrong serve. ---
if [[ -n "${LLM_ENDPOINT:-}" ]]; then
  uv run "${script_dir}/capture_serve_provenance.py" --label "${label}" \
    --out "${out_dir}/provenance.json" --endpoint "${LLM_ENDPOINT}" \
    || echo "warn: serve provenance capture failed (endpoint unreachable?)" >&2
else
  echo "warn: LLM_ENDPOINT unset — skipping serve provenance (set it to the serve URL to capture)" >&2
fi

pids=()

# --- reasoner-side recorder (default domain 0) ---
( export ROS_DOMAIN_ID="${reasoner_domain}"
  exec ros2 bag record --storage mcap -o "${out_dir}/${label}_reasoner_d${reasoner_domain}" \
    $(grep -vE '^\s*#|^\s*$' "${script_dir}/topics_domain0.txt") ) &
pids+=($!)

# --- perception/speech recorder (domain 200) ---
( export ROS_DOMAIN_ID=200
  exec ros2 bag record --storage mcap -o "${out_dir}/${label}_perception_d200" \
    $(grep -vE '^\s*#|^\s*$' "${script_dir}/topics_domain200.txt") ) &
pids+=($!)

# --- session label on both domains (1 Hz, so both bags carry the join key) ---
for dom in "${reasoner_domain}" 200; do
  ( export ROS_DOMAIN_ID="${dom}"
    exec ros2 topic pub -r 1 /profiling/session_label std_msgs/msg/String "{data: '${label}'}" ) &
  pids+=($!)
done

# --- goal-eval / TIMEDOUT redis sidecar (the proxy is pipeline-computed post-LLM, so it lives
#     on redis, not the litellm stream) ---
uv run "${script_dir}/redis_goaleval_logger.py" "${label}" \
  "${out_dir}/goal_eval.jsonl" --host "${REDIS_HOST:-127.0.0.1}" --port "${REDIS_PORT:-6379}" &
pids+=($!)

# --- per-service GPU memory sampler (host-side; see the header in gpu_apps_sampler.sh) ---
if command -v nvidia-smi >/dev/null 2>&1; then
  bash "${script_dir}/gpu_apps_sampler.sh" "${out_dir}/gpu_${label}.csv" 0.5 &
  pids+=($!)
else
  echo "warn: nvidia-smi not found on this host — GPU sampler skipped" >&2
fi

echo "profiling session '${label}' (reasoner domain ${reasoner_domain}): pids=${pids[*]}" >&2
echo "stop with Ctrl-C (or: kill -INT ${pids[*]})" >&2
trap 'kill -INT "${pids[@]}" 2>/dev/null' INT TERM
wait "${pids[@]}"
