# profiling/ — deployment session profiling (passive)

Five **passive observers** that reconstruct a live session's turn anatomy + GPU load. **Nothing
in the robot pipeline changes** — merged, this directory does nothing until an operator enables it.

## Why

Wall-clock at the **same breakpoints as the simulation profiling waterfall**, so demo sessions
are directly comparable to harness arms:

- **t0** = ASR result on the reasoner domain
- **per-agent LLM spans** = one row per completion (start/end/tokens)
- **TTFR** = first TTS "playing" edge after t0
- **turn anatomy** = the reply chain across ASR → agent outputs → TTS
- plus **per-service GPU memory** attribution (co-tenancy on a shared card)

## How

One command starts every sidecar and stops them together on Ctrl-C:

```bash
LLM_ENDPOINT=http://<serve-host>:<port> profiling/record_session.sh <label> [--reasoner-domain N]
```

`--reasoner-domain` defaults to **0** (this deployment). `<label>` names the output under
`profiling/out/<label>/` (gitignored) and is stamped into every artifact + a
`/profiling/session_label` topic.

Per-agent LLM spans are the one piece captured inside litellm. Enable them by registering the
callback in `config/llm/litellm_server.yaml` — the line is already present, **commented out**:

```yaml
  # callbacks: [litellm_post_fix.proxy_handler_instance, litellm_agent_spans.proxy_handler_instance]
```

Copy `profiling/litellm_agent_spans.py` next to the litellm config, set
`PROFILING_SPANS_PATH=profiling/out/<label>/agent_spans.jsonl`, and restart the llm service.

## Artifacts produced

| file | sidecar | answers |
|---|---|---|
| `<label>_reasoner_d0/` (mcap bag) | record_session.sh | t0, TTS edges, actions, reply chain, transcript |
| `<label>_perception_d200/` (mcap bag) | record_session.sh | ASR inner results, raw audio (re-ASR) |
| `goal_eval.jsonl` | redis_goaleval_logger.py | goal status incl. TIMEDOUT + criteria + elapsed |
| `provenance.json` | capture_serve_provenance.py | which serve answered (root/engine/quant/RTT) |
| `gpu_<label>.csv` | gpu_apps_sampler.sh | per-service GPU memory over the session |
| `agent_spans.jsonl` | litellm_agent_spans.py (callback) | per-agent LLM spans (start/end/tokens) |

## Turn it off

Delete the callback line (or leave it commented) and don't run `record_session.sh`. Nothing else
references this directory.

## Non-goals

No in-agent tracing, no behavior change, no data leaves the host — the sidecars only read topics /
subscribe to redis / sample nvidia-smi / append the litellm span.
