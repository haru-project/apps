#!/usr/bin/env bash
# Usage: bash profiling/record_session.sh <label>          (run from the repo root)
#
# Records one live session read-only: two ROS-bag recorders, serve-identity provenance, the
# goal-eval redis stream, and per-service GPU memory. Everything is keyed by <label> and stops
# together on Ctrl-C. Nothing is published into the ROS graph and no pipeline config changes.
#
# Domains default to this repo's HARU_ROBOT_ROS_DOMAIN_ID / HARU_PERCEPTION_ROS_DOMAIN_ID.
# Per-agent LLM spans are captured separately by a litellm callback — see profiling/README.md.
set -euo pipefail

label="${1:?usage: record_session.sh <label>}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Config comes from the repo's own variables (envs/all.env, envs/llm.env, start.sh), so a stack
# started with e.g. HARU_ROBOT_ROS_DOMAIN_ID=26 is recorded correctly instead of yielding empty
# bags. Export them into your shell, or run this with the same env the stack was started with.
robot_domain="${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}}"
perception_domain="${HARU_PERCEPTION_ROS_DOMAIN_ID:-200}"
topic_prefix="${HARU_TOPIC_PREFIX:-}"
# LLM_SERVER_BASE_URL is the repo's own name for the serve; strip its /v1 suffix.
endpoint="${HARU_PROFILING_LLM_ENDPOINT:-${LLM_SERVER_BASE_URL:-}}"
endpoint="${endpoint%/v1}"
out_dir="${HARU_PROFILING_OUT_DIR:-${script_dir}/out}/${label}"

# --- preflight: every external dependency, checked before anything is spawned ---
missing=()
command -v ros2 >/dev/null 2>&1 || missing+=("ros2 (source a ROS 2 environment, or run inside a ROS container)")
command -v uv   >/dev/null 2>&1 || missing+=("uv (the redis sidecar is a PEP-723 script)")
if [[ ${#missing[@]} -gt 0 ]]; then
  printf 'error: missing prerequisite: %s\n' "${missing[@]}" >&2
  echo "       see Prerequisites in profiling/README.md" >&2
  exit 1
fi
command -v nvidia-smi >/dev/null 2>&1 || echo "warn: nvidia-smi not found — GPU sampler will be skipped" >&2
[[ -n "${endpoint}" ]] || echo "warn: no LLM endpoint (set LLM_SERVER_BASE_URL or HARU_PROFILING_LLM_ENDPOINT) — skipping serve provenance" >&2

mkdir -p "${out_dir}"

pids=()
stop_all() { kill -INT "${pids[@]}" 2>/dev/null || true; }
trap stop_all INT TERM EXIT

# Session manifest, written BEFORE anything starts: the sidecars each timestamp their own rows,
# but only this script knows the session's boundaries and the config it ran under. Without it
# there is no recorded window to select a session's LLM spans by (they accumulate in one file
# across sessions — see litellm_agent_spans.py).
t_start="$(date +%s.%N)"
cat > "${out_dir}/session.json" <<EOF
{
  "label": "${label}",
  "t_start_unix": ${t_start},
  "tz_offset": "$(date +%z)",
  "host": "$(hostname)",
  "robot_domain": ${robot_domain},
  "perception_domain": ${perception_domain},
  "topic_prefix": "${topic_prefix}",
  "endpoint": "${endpoint}"
}
EOF

# --- one recorder per domain: robot side + perception/speech.
#     A single-domain recorder silently misses the other half of the session. ---
record_domain() {  # <domain> <name> <topic_file>
  local domain="$1" name="$2" topic_file="$3" topics=() line
  # tr -d '\r': a CRLF-saved topic file yields names that subscribe to nothing — an empty bag.
  while IFS= read -r line; do
    topics+=("${topic_prefix}${line}")
  done < <(grep -vE '^\s*#|^\s*$' "${topic_file}" | tr -d '\r')
  if [[ ${#topics[@]} -eq 0 ]]; then
    echo "error: no topics parsed from ${topic_file}" >&2
    exit 1
  fi
  ( export ROS_DOMAIN_ID="${domain}"
    exec ros2 bag record --storage mcap \
      -o "${out_dir}/${name}_d${domain}" "${topics[@]}" ) &
  pids+=($!)
}

record_domain "${robot_domain}" robot "${script_dir}/topics_robot.txt"
record_domain "${perception_domain}" perception "${script_dir}/topics_perception.txt"

# --- serve-identity provenance (HTTP, not a ROS topic). Backgrounded: it can wait on network
#     timeouts, and blocking here would drop the session's opening turns. ---
if [[ -n "${endpoint}" ]]; then
  ( "${script_dir}/capture_serve_provenance.py" --label "${label}" \
      --out "${out_dir}/provenance.json" --endpoint "${endpoint}" \
      || echo "warn: serve provenance capture failed (endpoint unreachable?)" >&2 ) &
  pids+=($!)
fi

# --- goal-eval / TIMEDOUT redis sidecar (the proxy is pipeline-computed post-LLM, so it lives
#     on redis, not the litellm stream) ---
"${script_dir}/redis_goaleval_logger.py" "${label}" "${out_dir}/goal_eval.jsonl" \
  --host "${REDIS_HOST:-127.0.0.1}" --port "${REDIS_PORT:-6379}" \
  --channel "${REDIS_CHANNEL:-haru_llm_dashboard}" &
pids+=($!)

# --- per-service GPU memory sampler (host-side; see the header in gpu_apps_sampler.sh) ---
if command -v nvidia-smi >/dev/null 2>&1; then
  bash "${script_dir}/gpu_apps_sampler.sh" "${out_dir}/gpu.csv" &
  pids+=($!)
fi

echo "profiling session '${label}' -> ${out_dir}" >&2
echo "  robot domain ${robot_domain}, perception domain ${perception_domain}" >&2
echo "stop with Ctrl-C" >&2

# `|| true`: on Ctrl-C the interrupted children make wait non-zero, and under `set -e` that would
# exit before the summary below runs.
wait "${pids[@]}" || true

printf '{"t_end_unix": %s}\n' "$(date +%s.%N)" > "${out_dir}/session_end.json"

# --- collect the stack's own logs for this session ---
# The LLM stack writes logs, conversation logs and its own profiling output to shared directories
# that are NOT session-scoped — they accumulate across runs. Selecting by modification time within
# this session's window files them by session automatically, so the copies here belong to <label>
# and only <label>. The originals are left untouched.
app_logs=0
app_data="${HARU_PROFILING_APP_DATA:-${script_dir}/../data/llm}"
for sub in logs conversation_logs profiling profling; do
  [[ -d "${app_data}/${sub}" ]] || continue
  while IFS= read -r -d '' f; do
    mkdir -p "${out_dir}/app_logs/${sub}"
    cp -p "${f}" "${out_dir}/app_logs/${sub}/" && app_logs=1
  done < <(find "${app_data}/${sub}" -type f -newermt "@${t_start%.*}" -print0 2>/dev/null)
done

# Report what actually landed. "Captured nothing" is only observable at the end, so a
# silently-empty artifact must not exit 0.
status=0
check() {  # <description> <test-result>
  if [[ "$2" == "ok" ]]; then echo "  OK    $1" >&2; else echo "  EMPTY $1" >&2; status=1; fi
}
for d in "${out_dir}"/*_d*/; do
  [[ -d "${d}" ]] || continue
  if compgen -G "${d}"'*.mcap' >/dev/null; then check "$(basename "${d}")" ok; else check "$(basename "${d}")" empty; fi
done
[[ -s "${out_dir}/goal_eval.jsonl" ]] && check goal_eval.jsonl ok || check goal_eval.jsonl empty
if command -v nvidia-smi >/dev/null 2>&1; then
  [[ "$(wc -l < "${out_dir}/gpu.csv" 2>/dev/null || echo 0)" -gt 1 ]] && check gpu.csv ok || check gpu.csv empty
fi
if [[ -n "${endpoint}" ]]; then
  [[ -s "${out_dir}/provenance.json" ]] && check provenance.json ok || check provenance.json empty
fi
# Not a failure if absent — the stack may be configured without these mounts.
if [[ "${app_logs}" -eq 1 ]]; then
  echo "  OK    app_logs/ ($(find "${out_dir}/app_logs" -type f | wc -l) files from ${app_data})" >&2
else
  echo "  none  app_logs/ (nothing written under ${app_data} during the session)" >&2
fi
exit "${status}"
