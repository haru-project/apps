from types import SimpleNamespace

from haru_configurator.discovery import _RobotListener, discover_robots


class _FakeZeroconf:
    def get_service_info(self, service_type: str, name: str, timeout: int):
        return SimpleNamespace(server="haru-19.local.")


def test_mdns_listener_normalizes_robot_hostname() -> None:
    listener = _RobotListener()
    listener.add_service(_FakeZeroconf(), "_ssh._tcp.local.", "haru-19._ssh._tcp.local.")
    assert listener.hosts == {"haru-19.local"}


def test_host_discovered_robots_seed_container_discovery(monkeypatch) -> None:
    monkeypatch.setenv(
        "HARU_DISCOVERED_ROBOTS",
        "haru-22.local,invalid-host,haru-3.local",
    )
    monkeypatch.setattr("haru_configurator.discovery.time.sleep", lambda _: None)

    assert discover_robots() == ["haru-3.local", "haru-22.local"]
