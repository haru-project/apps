# profiling/ — session profiling tooling (off by default)

Optional tooling for recording what a live session actually did and how long each part took.
It runs alongside the stack as an observer: **merged, this directory does nothing** until an
operator starts it, and it changes no pipeline behaviour.

## Why

Records timestamped evidence of what a session did, so sessions can be compared against each
other and against offline runs of the same pipeline. What it captures:

- **speech recognition events** — ASR results and their revisions, on both domains
- **per-agent LLM spans** — one row per completion (start/end/tokens)
- **speech output events** — TTS status, playback, and phoneme timing
- **action and goal state** — routines, action execution, and goal evaluation including timeouts
- **GPU memory per process** — how a shared card is divided while the session runs

Turn-level measures — when a turn starts, time to first response, the reply chain — are
**derived from these recordings during analysis**, not computed here.

For deriving turn start, the chain we observed on a running stack is:

```
/perception/proc/speech/asr/result   (SpeechToTextResult, reaches the robot domain via the bridge)
  → perception_postprocessors_node
  → /haru_context/add_conversation_item → context_translator_node
  → /haru_context/simple_context       → reasoner agents
```

So the ASR result is the utterance-in edge that begins a turn, but no reasoner agent subscribes
to it directly — a two-hop context translation sits in between, and all of those topics are
recorded. This was traced from the live pub/sub graph, not from timings; confirm it against your
own deployment before quoting a latency number.

## Prerequisites

Runs on the host where the stack is running, with the stack already up. Needs a **ROS 2
environment** (`ros2 bag record`), **`uv`** (the redis sidecar is a PEP-723 script), and
**`nvidia-smi`** for the GPU sampler. Missing prerequisites are reported before anything starts.

If the host has no ROS 2 install, run `record_session.sh` inside a ROS container that shares the
host's network and domains — but run `gpu_apps_sampler.sh` **separately on the host**, since
`nvidia-smi` inside a container cannot see other containers' GPU processes.

## How

Run from the repo root, with the same environment the stack was started with:

```bash
bash profiling/record_session.sh <label>
```

One command starts every sidecar and stops them together on Ctrl-C, then prints an OK/EMPTY line
per artifact and exits non-zero if anything came back empty. Output lands in
`profiling/out/<label>/` (gitignored; override with `HARU_PROFILING_OUT_DIR`).

Configuration is read from this repo's own variables, so a stack started with e.g.
`HARU_ROBOT_ROS_DOMAIN_ID=26 ./start.sh` is recorded correctly: `HARU_ROBOT_ROS_DOMAIN_ID` /
`HARU_PERCEPTION_ROS_DOMAIN_ID` (domains), `HARU_TOPIC_PREFIX` (prepended to every recorded
topic), `REDIS_HOST` / `REDIS_PORT` / `REDIS_CHANNEL`, and `LLM_SERVER_BASE_URL` (the serve to
capture identity from; override with `HARU_PROFILING_LLM_ENDPOINT`).

The endpoint is the base URL of the OpenAI-compatible serve — this repo's is
`LLM_SERVER_BASE_URL` minus its `/v1` suffix. Behind the litellm proxy the model-root and quant
fields come back empty and `errors` records what was unavailable; only a serve that exposes model
metadata (e.g. a local vLLM) fills them in.

### Per-agent LLM spans (optional, off by default)

Spans are the one piece captured inside litellm, so they need the container to see the module:

1. In `apps/docker-compose-llm.yaml`, uncomment the two `server` volume lines and the
   `environment:` block (all marked, all pointing at `profiling/`).
2. In `config/llm/litellm_server.yaml`, add `litellm_agent_spans.proxy_handler_instance` to the
   existing `callbacks:` list.
3. `bash scripts/compose.sh llm up server --force-recreate -d`

The module is mounted from `profiling/`, so there is no copy to keep in sync. Keep
`PROFILING_SPANS_PATH` stable across sessions and select a session's spans by time — the module
docstring explains why.

Two things to expect while spans are on: `test_profiling_spans_callback_is_off_by_default` fails
by design (it asserts the callback is unregistered), and if `agent_spans.jsonl` never appears,
check the container can write the mounted directory — the hook swallows its own errors so that it
can never fail a real completion.

## Artifacts produced

All under `profiling/out/<label>/`:

| file | source | answers |
|---|---|---|
| `session.json` + `session_end.json` | `record_session.sh` | when the session ran and under what config — the window everything else is sliced by |
| `robot_d<N>/` (mcap bag) | `topics_robot.txt` | ASR results, TTS events, actions, agent outputs, transcript |
| `perception_d<N>/` (mcap bag) | `topics_perception.txt` | ASR inner results, raw audio (re-ASR) |
| `goal_eval.jsonl` | `redis_goaleval_logger.py` | goal status incl. TIMEDOUT + criteria + elapsed |
| `provenance.json` | `capture_serve_provenance.py` | which serve answered (root/engine/quant/RTT) |
| `gpu.csv` | `gpu_apps_sampler.sh` | GPU memory per process over the session |

Plus one file **outside** the label directory: `profiling/out/agent_spans.jsonl`
(`litellm_agent_spans.py`) — per-agent LLM spans, appended across *all* sessions because the
container writes to a fixed path. Select one session's rows using `session.json`'s start/end.

Timestamps are Unix epoch everywhere except `gpu.csv`, which carries nvidia-smi's own formatted
column, forced to UTC so it joins without a timezone assumption. The GPU rows identify processes
by PID and process name; mapping those to containers is not done for you.

**Disk and privacy.** The perception bag records raw multi-channel audio, which dominates the
capture — check free space, and time a one-minute trial to size your own rate. Captures contain
what people said near the robot: audio in the perception bag, and utterance text in
`goal_eval.jsonl` (the dashboard conversation channel). Treat `profiling/out/` as personal data —
it is gitignored and nothing is uploaded anywhere.

## Turn it off

Remove `litellm_agent_spans.proxy_handler_instance` from the `callbacks:` list, re-comment the
`docker-compose-llm.yaml` lines, restart the llm service, and don't run `record_session.sh`.
No other code path imports anything from this directory. Turning it off does not delete captures
already in `profiling/out/` — remove those when you are done with them.

## Non-goals

No in-agent tracing. The sidecars only read ROS topics, subscribe to redis, sample `nvidia-smi`,
and append LLM spans — nothing is published into the ROS graph and no data leaves the host.
