#!/usr/bin/env python3
"""Capture the LLM serve identity for a profiling session.

Records what is needed to know exactly which serve answered this session (and to replicate it):
resolved model root, alias, whatever /version returns, quant, endpoint URL + host, and a
round-trip latency stamp (matters when the serve is remote — the network hop is on the record).

The endpoint must be given explicitly (--endpoint, or the caller's LLM_SERVER_BASE_URL): there is
no localhost default, so a run cannot silently pin the wrong serve when the real one is elsewhere.

Stdlib only, like the rest of this repo's python.

Usage: capture_serve_provenance.py --label <label> --out <provenance.json> --endpoint URL
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

QUANT_HINTS = ("bf16", "fp16", "fp8", "int4", "int8", "awq", "gptq", "qat")
HTTP_ERRORS = (urllib.error.URLError, OSError, ValueError, KeyError, IndexError)


def derive_quant(root: str) -> str | None:
    """Read the quantisation out of a served model name, e.g. .../gemma-4-26b-AWQ-INT4."""
    low = (root or "").lower()
    hits = [q for q in QUANT_HINTS if q in low]
    return "+".join(hits) if hits else None


def get_json(url: str, timeout: float) -> tuple[dict, float]:
    """GET one JSON document; return it with the round-trip time in milliseconds."""
    t0 = time.time()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        payload = json.load(resp)
    return payload, (time.time() - t0) * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--endpoint", required=True)
    args = ap.parse_args()

    base = args.endpoint.rstrip("/")
    host = urlparse(base if "//" in base else "http://" + base).hostname
    prov: dict = {"session_label": args.label, "endpoint_url": base, "endpoint_host": host,
                  "capture_unix": time.time(), "errors": []}
    rtts: list[float] = []

    # /v1/models — resolved root + alias + context length
    try:
        payload, rtt = get_json(f"{base}/v1/models", timeout=10)
        served = payload["data"][0]
        prov.update(llm_served_root=served.get("root"), llm_alias=served.get("id"),
                    max_model_len=served.get("max_model_len"),
                    quant=derive_quant(served.get("root", "")))
        rtts.append(rtt)
    except HTTP_ERRORS as exc:
        prov["errors"].append(f"/v1/models: {exc}")

    # /version, if the serve exposes one. Recorded verbatim — do NOT label it, since a proxy may
    # answer here too and asserting an engine name would put a false provenance claim on record.
    try:
        prov["version_endpoint"], _ = get_json(f"{base}/version", timeout=5)
    except HTTP_ERRORS as exc:
        prov["errors"].append(f"/version: {exc}")

    # A few more pings so a remote-serve network hop is on the record.
    for _ in range(3):
        try:
            _, rtt = get_json(f"{base}/v1/models", timeout=5)
            rtts.append(rtt)
        except HTTP_ERRORS:
            break
    if rtts:
        prov["rtt_ms_median"] = round(statistics.median(rtts), 1)
        prov["rtt_samples"] = len(rtts)

    args.out.write_text(json.dumps(prov, indent=2), encoding="utf-8")
    print(json.dumps(prov, indent=2))


if __name__ == "__main__":
    main()
