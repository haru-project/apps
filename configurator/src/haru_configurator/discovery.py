"""Host-side deployment probes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import re
import socket
import subprocess
import time

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf


ROBOT_PATTERN = re.compile(r"^(haru-\d+)(?:\.local)?\.?$", re.IGNORECASE)


class _RobotListener(ServiceListener):
    def __init__(self) -> None:
        self.hosts: set[str] = set()

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        info = zeroconf.get_service_info(service_type, name, timeout=300)
        candidates = [name.split("._", 1)[0]]
        if info and info.server:
            candidates.append(info.server.rstrip("."))
        for candidate in candidates:
            match = ROBOT_PATTERN.fullmatch(candidate)
            if match:
                self.hosts.add(f"{match.group(1).lower()}.local")

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self.add_service(zeroconf, service_type, name)

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        return


def _resolves(host: str) -> str | None:
    try:
        socket.getaddrinfo(host, None, family=socket.AF_INET)
    except OSError:
        return None
    return host


def discover_robots(timeout: float = 2.0) -> list[str]:
    """Discover robots with mDNS services, then bounded hostname probing."""
    listener = _RobotListener()
    zeroconf = Zeroconf()
    browsers = [
        ServiceBrowser(zeroconf, service_type, listener)
        for service_type in ("_ssh._tcp.local.", "_workstation._tcp.local.")
    ]
    try:
        time.sleep(timeout)
    finally:
        for browser in browsers:
            browser.cancel()
        zeroconf.close()

    scan_max = int(os.environ.get("HARU_DISCOVERY_MAX_ID", "64"))
    candidates = [f"haru-{index}.local" for index in range(1, scan_max + 1)]
    with ThreadPoolExecutor(max_workers=32) as executor:
        listener.hosts.update(filter(None, executor.map(_resolves, candidates)))
    return sorted(listener.hosts, key=lambda host: int(re.search(r"\d+", host).group()))


def host_reachable(host: str) -> bool:
    return _resolves(host) is not None


def audio_devices() -> str:
    try:
        return subprocess.run(
            ["arecord", "-l"], check=False, capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def has_display() -> bool:
    return bool(os.environ.get("DISPLAY"))


def has_nvidia_gpu() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{json .Runtimes}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "nvidia" in result.stdout.lower()
