# profiling/ — session profiling tooling (off by default)

Optional tooling for recording what a live session actually did and how long each part took.
It runs alongside the stack as an observer: **merged, this directory does nothing** until an
operator starts it, and it changes no pipeline behaviour.

## Why

Records wall-clock timestamps at fixed points in a turn, so sessions can be compared against
each other and against offline runs of the same pipeline:

- **t0** — the ASR result that starts a turn
- **per-agent LLM spans** — one row per completion (start/end/tokens)
- **TTFR** (time to first response) — the first TTS "playing" edge after t0
- **turn anatomy** — the reply chain across ASR → agent outputs → TTS
- **per-service GPU memory** — which container holds what on a shared card

## Prerequisites

Runs on the host where the stack is running, with the stack already up. Needs a **ROS 2
environment** (`ros2 bag record`), **`uv`** (the two `.py` sidecars are PEP-723 self-contained),
and **`nvidia-smi`** for the GPU sampler (skipped with a warning if absent).

If the host has no ROS 2 install, run `record_session.sh` inside a ROS container that shares the
host's network and domains — but run `gpu_apps_sampler.sh` **separately on the host**, since
`nvidia-smi` inside a container cannot see other containers' GPU processes.

## How

```bash
LLM_ENDPOINT=http://<serve-host>:<port> bash profiling/record_session.sh <label>
```

Run from the repo root. One command starts every sidecar and stops them together on Ctrl-C.
Output lands in `profiling/out/<label>/` (gitignored).

Domains default to this repo's own `HARU_ROBOT_ROS_DOMAIN_ID` / `HARU_PERCEPTION_ROS_DOMAIN_ID`,
so a stack started with e.g. `HARU_ROBOT_ROS_DOMAIN_ID=26 ./start.sh` is recorded correctly.
Also reads `REDIS_HOST` / `REDIS_PORT` / `REDIS_CHANNEL` (defaults `127.0.0.1:6379`,
`haru_llm_dashboard`).

`LLM_ENDPOINT` should point at the OpenAI-compatible serve that actually answers completions.
Against a hosted-model proxy rather than a local vLLM, the model-root/quant/engine fields come
back empty and `errors` is populated — that is expected, not a failure.

### Per-agent LLM spans (optional, off by default)

Spans are the one piece captured inside litellm, so they need the container to see the module:

1. In `apps/docker-compose-llm.yaml`, uncomment the two `server` volume lines and the
   `environment:` block (all marked, all pointing at `profiling/`).
2. In `config/llm/litellm_server.yaml`, add `litellm_agent_spans.proxy_handler_instance` to the
   existing `callbacks:` list.
3. `bash scripts/compose.sh llm up server --force-recreate -d`

The module is **mounted** from `profiling/`, never copied — there is no second copy to drift.
Use one stable `PROFILING_SPANS_PATH` across sessions and select a session's spans by time; the
module docstring explains why.

## Artifacts produced

| file | source | answers |
|---|---|---|
| `<label>_robot_d<N>/` (mcap bag) | `topics_robot.txt` | t0, TTS edges, actions, reply chain, transcript |
| `<label>_perception_d<N>/` (mcap bag) | `topics_perception.txt` | ASR inner results, raw audio (re-ASR) |
| `goal_eval.jsonl` | `redis_goaleval_logger.py` | goal status incl. TIMEDOUT + criteria + elapsed |
| `provenance.json` | `capture_serve_provenance.py` | which serve answered (root/engine/quant/RTT) |
| `gpu_<label>.csv` | `gpu_apps_sampler.sh` | per-service GPU memory over the session |
| `agent_spans.jsonl` | `litellm_agent_spans.py` (callback) | per-agent LLM spans (start/end/tokens) |

**Disk and privacy.** The perception bag records raw audio — budget roughly a gigabyte per
minute and check free space before starting. Captures contain participants' voices (and any
person state the robot published), so treat `profiling/out/` as personal data: it is gitignored
and nothing is uploaded anywhere.

## Turn it off

Remove `litellm_agent_spans.proxy_handler_instance` from the `callbacks:` list, re-comment the
`docker-compose-llm.yaml` lines, restart the llm service, and don't run `record_session.sh`.
No other code path imports anything from this directory.

## Non-goals

No in-agent tracing. The sidecars only read ROS topics, subscribe to redis, sample `nvidia-smi`,
and append LLM spans — nothing is published into the ROS graph and no data leaves the host.
