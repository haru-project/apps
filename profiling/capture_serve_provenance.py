#!/usr/bin/env python3
"""Capture the LLM serve identity for a profiling session.

Records what is needed to know exactly which serve answered this session (and to replicate it):
resolved model root, alias, whatever /version returns, quant, endpoint URL + host, and a
round-trip latency stamp (matters when the serve is remote — the network hop is on the record).

When the endpoint is a litellm proxy, /v1/models returns only the ALIAS (e.g. "haru:canonical"),
which says nothing about the weights behind it. /model/info is queried as well because that is
the only place the routing table is exposed. An alias is a request; the route is the observation.

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
        models = payload.get("data") or []
        prov["models_exposed"] = [m.get("id") for m in models]
        if len(models) == 1:
            # A direct serve: the single entry IS the model that answered.
            served = models[0]
            prov.update(llm_served_root=served.get("root"), llm_alias=served.get("id"),
                        max_model_len=served.get("max_model_len"),
                        quant=derive_quant(served.get("root", "")))
        else:
            # A gateway fronting many models. Taking data[0] would put an arbitrary model on
            # record as "the" serve — on the dgx02 litellm gateway that is gpt-4o-mini, which
            # answered nothing. Leave the single-model fields unset; alias_routes below is the
            # honest record of what this endpoint can reach.
            prov["multi_model_endpoint"] = True
        rtts.append(rtt)
    except HTTP_ERRORS as exc:
        prov["errors"].append(f"/v1/models: {exc}")

    # /model/info — a litellm proxy resolves its aliases here, and ONLY here. /v1/models returns
    # the alias by itself, so a session fronted by a proxy otherwise records "haru:canonical" and
    # nothing about which weights actually answered — the gap that left 12 sessions on 2026-08-20
    # unattributable. A 404 is normal and expected against a direct vLLM serve.
    try:
        info, _ = get_json(f"{base}/model/info", timeout=10)
        prov["alias_routes"] = {
            entry["model_name"]: {
                "model": (entry.get("litellm_params") or {}).get("model"),
                "api_base": (entry.get("litellm_params") or {}).get("api_base"),
            }
            for entry in (info.get("data") or [])
            if entry.get("model_name")
        }
    except HTTP_ERRORS as exc:
        prov["errors"].append(f"/model/info (normal if not a litellm proxy): {exc}")

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
