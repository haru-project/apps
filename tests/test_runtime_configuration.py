from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_robot_domain_is_wired_through_canonical_override() -> None:
    fallback = "${HARU_ROBOT_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID:-0}}"
    assert fallback in (ROOT / "apps/compose.common.yaml").read_text()
    assert fallback in (ROOT / "apps/docker-compose-all.yaml").read_text()
    assert fallback in (ROOT / "apps/docker-compose-memory.yaml").read_text()
    assert fallback in (ROOT / "apps/docker-compose-timeline-player.yaml").read_text()


def test_persons_bridge_matches_reliable_source() -> None:
    bridge_config = (ROOT / "config/domain_bridge.yaml").read_text()
    persons_config = bridge_config.split(
        "  /perception/fusion/persons:\n", maxsplit=1
    )[1].split("\n  /perception/fusion/speech_sources:", maxsplit=1)[0]
    assert "remap:" not in persons_config
    assert "reliability: reliable" in persons_config
    assert "durability: volatile" in persons_config
    assert "history: keep_last" in persons_config
    assert "depth: 1" in persons_config

    bridge_compose = (ROOT / "apps/docker-compose-domain-bridge.yaml").read_text()
    all_compose = (ROOT / "apps/docker-compose-all.yaml").read_text()
    assert "persons-qos-relay" not in bridge_compose
    assert "persons-qos-relay" not in all_compose


def test_downloaders_handle_profiled_and_root_owned_data() -> None:
    speech_downloader = (ROOT / "scripts/download_speech_data.sh").read_text()
    assert '--entrypoint chmod' in speech_downloader
    assert 'chmod -R a+rwX "$MODELS_FOLDER"' not in speech_downloader

    nlp_downloader = (ROOT / "scripts/download_nlp_data.sh").read_text()
    assert "--profile cpu" in nlp_downloader
    assert "--no-deps" in nlp_downloader
    assert "haru-nlp-server-cpu" in nlp_downloader
    assert "haru-nlp-server\n" not in nlp_downloader
    assert "--entrypoint chmod" in nlp_downloader
    assert '--project-name "haru-nlp-data-download-${BASHPID}"' in nlp_downloader
    assert "down --remove-orphans" in nlp_downloader


def test_stop_enables_every_compose_profile() -> None:
    stop_script = (ROOT / "stop.sh").read_text()
    compose_down_lines = [
        line
        for line in stop_script.splitlines()
        if "scripts/compose.sh" in line and line.endswith(" down")
    ]
    assert compose_down_lines
    assert all('--profile "*" down' in line for line in compose_down_lines)
    assert "docker system prune" not in stop_script
