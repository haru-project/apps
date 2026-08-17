#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["redis"]
# ///
"""Redis subscriber-logger: persist the goal-eval / TIMEDOUT stream for one profiling session.

The haru-llm pipeline publishes per-turn action + goal-eval state to redis (`DashboardPublisher`,
constructed in `action_args.py`). The payload carries `evaluation.status` (GoalStatus enum incl.
TIMEDOUT), per-criterion CriterionStatus, timeout config, and turns/time elapsed. The goal
TIMEOUT signal is computed post-LLM by the pipeline, so it lives here, NOT in the litellm stream.
That pub/sub stream is EPHEMERAL — this logger persists it to a labeled JSONL so it survives.

Runs on the host (redis 6379 is host-exposed). Subscribes to the real-time `<channel>:updates`
pub/sub; each message is written with a receive timestamp and the session label. Also snapshots
the current state key at startup. Read-only: subscribes, never publishes.

Usage: redis_goaleval_logger.py <label> <out.jsonl> [--host H] [--port P] [--channel C]
"""
import argparse
import json
import time

import redis


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session_id")
    ap.add_argument("out")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=6379)
    ap.add_argument("--channel", default="haru_llm_dashboard")
    a = ap.parse_args()

    r = redis.Redis(host=a.host, port=a.port, decode_responses=True)
    out = open(a.out, "w")

    def write(kind, payload):
        rec = {"t_recv": time.time(), "session_id": a.session_id, "kind": kind, "payload": payload}
        out.write(json.dumps(rec) + "\n")
        out.flush()

    # startup snapshot of the state key (latest message) — corroborating evidence
    snap = r.get(a.channel)
    if snap:
        write("state_snapshot", _safe_json(snap))

    ps = r.pubsub()
    ps.subscribe(f"{a.channel}:updates", f"{a.channel}:conversation")
    print(f"subscribed: {a.channel}:updates (+:conversation) — logging to {a.out}", flush=True)
    for m in ps.listen():
        if m.get("type") != "message":
            continue
        # Record which channel it came from — the two carry different payloads.
        channel = (m.get("channel") or "").rsplit(":", 1)[-1]
        write(channel or "update", _safe_json(m.get("data")))


def _safe_json(s):
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return s


if __name__ == "__main__":
    main()
