#!/usr/bin/env python3
"""Align downloaded Agent Memory connection settings with rendered Compose values."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _port(value: str) -> str:
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError(f"port must be between 1 and 65535: {value}")
    return str(port)


def rewrite_weaviate_connection(
    config_path: Path,
    host: str,
    http_port: str,
    grpc_port: str,
) -> None:
    if not host:
        raise ValueError("Weaviate host must not be empty")

    replacements = {
        "weaviate_host": json.dumps(host),
        "weaviate_port": _port(http_port),
        "weaviate_grpc_port": _port(grpc_port),
    }
    text = config_path.read_text(encoding="utf-8")

    for key, value in replacements.items():
        pattern = re.compile(rf"^(\s+{re.escape(key)}:\s*).*$", re.MULTILINE)
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise ValueError(
                f"expected exactly one {key!r} setting in {config_path}, "
                f"found {len(matches)}"
            )
        text = pattern.sub(lambda match: f"{match.group(1)}{value}", text, count=1)

    config_path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", type=Path)
    parser.add_argument("host")
    parser.add_argument("http_port")
    parser.add_argument("grpc_port")
    args = parser.parse_args()
    rewrite_weaviate_connection(
        args.config_path,
        args.host,
        args.http_port,
        args.grpc_port,
    )


if __name__ == "__main__":
    main()
