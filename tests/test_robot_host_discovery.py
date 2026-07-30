from __future__ import annotations

import importlib.util
from pathlib import Path
import socket


ROOT = Path(__file__).resolve().parents[1]


def _load_discovery_script():
    path = ROOT / "scripts/discover_robot_hosts.py"
    spec = importlib.util.spec_from_file_location("discover_robot_hosts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_host_discovery_returns_resolvable_robot_names() -> None:
    def resolver(host: str, _port, *, family: int):
        assert family == socket.AF_INET
        if host == "haru-19.local":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.55.195", 0))]
        raise socket.gaierror

    discovered = _load_discovery_script().discover_robot_hosts(20, resolver)

    assert discovered == [("haru-19.local", "192.168.55.195")]
