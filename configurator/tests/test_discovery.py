from types import SimpleNamespace

from haru_configurator.discovery import _RobotListener


class _FakeZeroconf:
    def get_service_info(self, service_type: str, name: str, timeout: int):
        return SimpleNamespace(server="haru-19.local.")


def test_mdns_listener_normalizes_robot_hostname() -> None:
    listener = _RobotListener()
    listener.add_service(_FakeZeroconf(), "_ssh._tcp.local.", "haru-19._ssh._tcp.local.")
    assert listener.hosts == {"haru-19.local"}
