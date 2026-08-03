#!/usr/bin/env python3
"""Resolve bounded Haru robot hostnames through the host's NSS configuration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import socket
from collections.abc import Callable


Resolver = Callable[..., list[tuple]]


def discover_robot_hosts(
    max_id: int,
    resolver: Resolver = socket.getaddrinfo,
) -> list[tuple[str, str]]:
    def resolve(index: int) -> tuple[str, str] | None:
        host = f"haru-{index}.local"
        try:
            records = resolver(host, None, family=socket.AF_INET)
        except OSError:
            return None
        addresses = sorted({record[4][0] for record in records})
        return (host, addresses[0]) if addresses else None

    workers = max(1, min(max_id, 64))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        discovered = filter(None, executor.map(resolve, range(1, max_id + 1)))
        return list(discovered)


def main() -> None:
    max_id = int(os.environ.get("HARU_DISCOVERY_MAX_ID", "64"))
    if not 1 <= max_id <= 232:
        raise ValueError("HARU_DISCOVERY_MAX_ID must be between 1 and 232")
    for host, address in discover_robot_hosts(max_id):
        print(f"{host}\t{address}")


if __name__ == "__main__":
    main()
