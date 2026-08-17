"""Per-agent LLM span logger — one JSONL row per completion, for waterfall reconstruction.

A litellm CustomLogger (same machinery as the sibling litellm_post_fix.py). Its success hook
carries the call's start/end times, so it emits the per-agent LLM span the deployment waterfall
needs: {ts_start, ts_end, latency_s, model, agent, tokens_in/out, sys_fingerprint}. All agents
share one model alias, so `agent` is taken from request metadata when present and a short system-
prompt fingerprint is included so downstream attribution can disambiguate.

PASSIVE + fail-safe: it only appends to a file and must never turn a successful call into a
failure. It is off unless an operator registers the callback — see profiling/README.md.

Output path = env PROFILING_SPANS_PATH (default ./agent_spans.jsonl), read once at import. Use
ONE stable path for all sessions rather than a per-session file: changing it means restarting the
LLM service (a model reload), and a forgotten restart silently files spans under the previous
session. Every row carries ts_start/ts_end, so a session's spans are selected by time window.

ts_start/ts_end come from litellm. If it hands back naive datetimes they are read in the
container's local zone, so each row also carries t_logged — an epoch stamp taken here, on the
same clock as the other sidecars — which makes any offset visible rather than silently shifting
the whole span timeline.
"""

import json
import os
import time

from litellm.integrations.custom_logger import CustomLogger

_OUT = os.environ.get("PROFILING_SPANS_PATH", "agent_spans.jsonl")


class AgentSpanLogger(CustomLogger):
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            meta = (kwargs.get("litellm_params") or {}).get("metadata") or {}
            msgs = kwargs.get("messages") or []
            sys_msg = next((m.get("content", "") for m in msgs if m.get("role") == "system"), "")
            usage = getattr(response_obj, "usage", None)
            row = {
                "ts_start": start_time.timestamp(),
                "ts_end": end_time.timestamp(),
                "t_logged": time.time(),  # epoch on the sidecars' clock; see the docstring
                "latency_s": (end_time - start_time).total_seconds(),
                "model": kwargs.get("model"),
                "agent": meta.get("agent") or meta.get("tags"),
                "sys_fingerprint": sys_msg[:120],
                "tokens_in": getattr(usage, "prompt_tokens", None),
                "tokens_out": getattr(usage, "completion_tokens", None),
            }
            with open(_OUT, "a") as fh:
                fh.write(json.dumps(row) + "\n")
        except Exception:
            # A profiling hook must never turn a successful model call into a failure.
            pass


proxy_handler_instance = AgentSpanLogger()
