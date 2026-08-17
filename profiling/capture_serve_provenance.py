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

Usage: capture_serve_provenance.py --label <label> --out <provenance.json> [--endpoint URL] [--quant Q]
"""
import argparse
import json
import os
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
    ap.add_argument("--quant", default=os.environ.get("LLM_QUANT"),
                    help="explicit quant (e.g. bf16); wins over root-derived so the field is "
                         "never blank even when the root name does not encode it.")
    a = ap.parse_args()

    if not a.endpoint:
        print("error: --endpoint or LLM_ENDPOINT required (no localhost default — a wrong "
              "endpoint pins the wrong serve)", file=sys.stderr)
        sys.exit(2)

    base = a.endpoint.rstrip("/")
    host = urlparse(base if "//" in base else "http://" + base).hostname
    prov = {"session_label": a.label, "endpoint_url": base, "endpoint_host": host,
            "capture_unix": time.time(), "errors": []}
    # explicit --quant wins and is set FIRST, so the field is never blank even if /v1/models
    # is unreachable; root-derived is kept for cross-check.
    if a.quant:
        prov["quant"] = a.quant
        prov["quant_source"] = "explicit"

    # /v1/models — resolved root + alias + context
    try:
        t0 = time.time()
        r = requests.get(f"{base}/v1/models", timeout=10)
        rtt = (time.time() - t0) * 1000
        d = r.json()["data"][0]
        derived = derive_quant(d.get("root", ""))
        prov.update(llm_served_root=d.get("root"), llm_alias=d.get("id"),
                    max_model_len=d.get("max_model_len"),
                    quant_derived=derived, models_rtt_ms=round(rtt, 1))
        if not a.quant:  # fall back to derived only when no explicit override
            prov["quant"] = derived
            prov["quant_source"] = "root-derived"
    except (requests.RequestException, KeyError, ValueError, IndexError) as e:
        prov["errors"].append(f"/v1/models: {e}")

    # engine name + version (vLLM exposes /version; best-effort)
    try:
        v = requests.get(f"{base}/version", timeout=5).json()
        prov["engine"] = {"name": "vllm", "version": v.get("version")}
    except (requests.RequestException, ValueError) as e:
        prov["errors"].append(f"/version: {e}")

    # LAN round-trip stamp — median of a few /v1/models pings (the remote-serve hop on the record)
    rtts = []
    for _ in range(5):
        try:
            t0 = time.time()
            requests.get(f"{base}/v1/models", timeout=5)
            rtts.append((time.time() - t0) * 1000)
        except requests.RequestException:
            break
    if rtts:
        rtts.sort()
        prov["lan_rtt_ms"] = {"median": round(rtts[len(rtts) // 2], 1),
                              "min": round(rtts[0], 1), "max": round(rtts[-1], 1), "n": len(rtts)}

    with open(a.out, "w") as fh:
        json.dump(prov, fh, indent=2)
    print(json.dumps({k: prov.get(k) for k in
                      ("endpoint_host", "llm_served_root", "quant", "lan_rtt_ms", "errors")}, indent=2))


if __name__ == "__main__":
    main()
