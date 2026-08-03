from pathlib import Path

from ruamel.yaml import YAML


RENAMED_SERVICES = {
    ("docker-compose-ipad.yaml", "server"): "ipad-server",
    ("docker-compose-projector.yaml", "server"): "projector-server",
    ("docker-compose-nlp.yaml", "redis"): "nlp-redis",
    ("docker-compose-timeline-player.yaml", "dev"): "timeline-player-dev",
}


def test_all_compose_includes_every_component_service() -> None:
    root = Path(__file__).resolve().parents[2]
    apps = root / "apps"
    yaml = YAML(typ="rt")
    with (apps / "docker-compose-all.yaml").open(encoding="utf-8") as stream:
        aggregate = yaml.load(stream)["services"]

    component_files = sorted(apps.glob("docker-compose-*.yaml"))
    component_files = [
        path
        for path in component_files
        if path.name not in {"docker-compose-all.yaml"}
    ]
    missing: list[str] = []
    for path in component_files:
        with path.open(encoding="utf-8") as stream:
            services = (yaml.load(stream) or {}).get("services", {})
        for source_name in services:
            aggregate_name = RENAMED_SERVICES.get((path.name, source_name), source_name)
            service = aggregate.get(aggregate_name)
            expected = {"file": path.name, "service": source_name}
            if not service or service.get("extends") != expected:
                missing.append(f"{path.name}:{source_name} -> {aggregate_name}")

    assert not missing, "Missing aggregate services:\n" + "\n".join(missing)


def test_local_nlp_excludes_server_observability_and_custom_network() -> None:
    root = Path(__file__).resolve().parents[2]
    yaml = YAML(typ="rt")
    nlp = yaml.load((root / "apps" / "docker-compose-nlp.yaml").read_text())
    aggregate = yaml.load((root / "apps" / "docker-compose-all.yaml").read_text())

    for service in ("loki", "tempo", "prometheus", "grafana"):
        assert service not in nlp["services"]
        assert service not in aggregate["services"]
    assert "haru-nlp-server" not in nlp.get("networks", {})
    assert "haru-nlp-server" not in aggregate.get("networks", {})
    assert nlp["services"]["haru-nlp-server-cpu"]["profiles"] == ["cpu"]
    assert nlp["services"]["haru-nlp-server-gpu"]["profiles"] == ["gpu"]
