#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""Capture the LLM serve identity for a profiling session.

Records what is needed to know exactly which serve answered this session (and to replicate it):
resolved model root, alias, engine name+version, quant, endpoint URL + host, and a round-trip
latency stamp (matters when the serve is remote — the network hop is on the record).

Endpoint MUST be given (--endpoint or LLM_ENDPOINT) — there is no localhost default, so a run
cannot silently pin the wrong serve when the real one is elsewhere.

Usage: capture_serve_provenance.py --label <label> --out <provenance.json> [--endpoint URL]
"""
import argparse
import json
import os
import statistics
import sys
import time
from urllib.parse import urlparse

import requests

QUANT_HINTS = ("bf16", "fp16", "fp8", "int4", "int8", "awq", "gptq", "qat")


def derive_quant(root: str) -> str | None:
    low = (root or "").lower()
    hits = [q for q in QUANT_HINTS if q in low]
    return "+".join(hits) if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--endpoint", default=os.environ.get("LLM_ENDPOINT"))
    a = ap.parse_args()

    if not a.endpoint:
        print("error: --endpoint or LLM_ENDPOINT required (no localhost default — a wrong "
              "endpoint pins the wrong serve)", file=sys.stderr)
        sys.exit(2)

    base = a.endpoint.rstrip("/")
    host = urlparse(base if "//" in base else "http://" + base).hostname
    prov = {"session_label": a.label, "endpoint_url": base, "endpoint_host": host,
            "capture_unix": time.time(), "errors": []}
    rtts = []  # round-trip samples, seeded by the /v1/models call below
    # /v1/models — resolved root + alias + context
    try:
        t0 = time.time()
        r = requests.get(f"{base}/v1/models", timeout=10)
        rtt = (time.time() - t0) * 1000
        d = r.json()["data"][0]
        prov.update(llm_served_root=d.get("root"), llm_alias=d.get("id"),
                    max_model_len=d.get("max_model_len"),
                    quant=derive_quant(d.get("root", "")))
        rtts.append(rtt)
    except (requests.RequestException, KeyError, ValueError, IndexError) as e:
        prov["errors"].append(f"/v1/models: {e}")

    # engine name + version (vLLM exposes /version; best-effort)
    try:
        v = requests.get(f"{base}/version", timeout=5).json()
        prov["engine"] = {"name": "vllm", "version": v.get("version")}
    except (requests.RequestException, ValueError) as e:
        prov["errors"].append(f"/version: {e}")

    # Round-trip stamp — a few more /v1/models pings, so a remote-serve network hop is on the
    # record alongside the timings it inflates.
    for _ in range(3):
        try:
            t0 = time.time()
            requests.get(f"{base}/v1/models", timeout=5)
            rtts.append((time.time() - t0) * 1000)
        except requests.RequestException:
            break
    if rtts:
        prov["rtt_ms"] = {"median": round(statistics.median(rtts), 1), "min": round(min(rtts), 1),
                          "max": round(max(rtts), 1), "n": len(rtts)}

    with open(a.out, "w") as fh:
        json.dump(prov, fh, indent=2)
    print(json.dumps(prov, indent=2))


if __name__ == "__main__":
    main()
