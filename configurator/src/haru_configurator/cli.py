"""Single public CLI for guided setup and demo lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import urllib.request

import questionary
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table
from ruamel.yaml import YAML
import typer

from .configuration import ConfigurationWriter, has_provider_secret, load_answers
from .discovery import (
    audio_devices,
    discover_robots,
    has_display,
    has_nvidia_gpu,
    host_reachable,
    port_available,
)
from .models import Deployment, LLMProvider, PROVIDER_DEFAULTS, SetupAnswers
from .orchestration import Orchestrator, data_is_present
from .scenario import DEFAULT_SCENARIO, ScenarioManager


app = typer.Typer(no_args_is_help=True, help="Configure and operate a local Haru deployment.")
scenario_app = typer.Typer(no_args_is_help=True, help="Run and stop task scenarios safely.")
app.add_typer(scenario_app, name="scenario")
console = Console()


def repo_root() -> Path:
    value = os.environ.get("HARU_REPO_ROOT")
    if not value:
        raise RuntimeError("HARU_REPO_ROOT is not set; use the repository setup.sh launcher")
    root = Path(value).resolve()
    expected = (root / "configurator" / "schema-version").read_text(encoding="utf-8").strip()
    actual = os.environ.get("HARU_CONFIGURATOR_SCHEMA_VERSION", "")
    if expected != actual:
        raise RuntimeError(f"Configurator/repository schema mismatch: image={actual!r}, repo={expected!r}")
    return root


def ask(prompt) -> object:
    result = prompt.ask()
    if result is None:
        raise typer.Abort()
    return result


def interactive_answers() -> tuple[SetupAnswers, str | None]:
    console.print("[bold]Haru local deployment setup[/bold]")
    robots = discover_robots()
    if robots:
        console.print(f"Discovered robots: {', '.join(robots)}")
    deployment = Deployment(
        ask(
            questionary.select(
                "Deployment target",
                choices=[
                    questionary.Choice("Physical robot", Deployment.PHYSICAL.value),
                    questionary.Choice("Simulator", Deployment.SIMULATOR.value),
                ],
            )
        )
    )
    robot_host = None
    if deployment == Deployment.PHYSICAL:
        choices = [questionary.Choice(host, host) for host in robots]
        choices.append(questionary.Choice("Enter another hostname", "manual"))
        selected = ask(questionary.select("Select the robot", choices=choices))
        robot_host = (
            str(ask(questionary.text("Robot hostname", default="haru-1.local"))).strip()
            if selected == "manual"
            else str(selected)
        )
        if not host_reachable(robot_host):
            proceed = ask(questionary.confirm(f"{robot_host} does not resolve yet. Save it anyway?", default=False))
            if not proceed:
                raise typer.Abort()

    devices = audio_devices()
    gpu = has_nvidia_gpu()
    if not gpu:
        proceed = ask(
            questionary.confirm(
                "The NVIDIA Docker runtime was not detected. Save this GPU-dependent deployment anyway?",
                default=False,
            )
        )
        if not proceed:
            raise typer.Abort()
    zoom_detected = "ZOOM" in devices.upper()
    kinect_detected = "KINECT" in devices.upper() or Path("/run/udev").exists()
    zoom = bool(ask(questionary.confirm("Enable Zoom H8 speech input?", default=zoom_detected)))
    kinect = bool(ask(questionary.confirm("Enable Azure Kinect perception?", default=kinect_detected)))
    kinect_speech = False
    if kinect:
        kinect_speech = bool(
            ask(questionary.confirm("Enable Kinect microphone transcription?", default=False))
        )

    provider = LLMProvider(
        ask(
            questionary.select(
                "LLM provider",
                choices=[
                    questionary.Choice("AWS Bedrock Gemma (recommended)", "bedrock"),
                    questionary.Choice("OpenAI", "openai"),
                    questionary.Choice("Anthropic", "anthropic"),
                    questionary.Choice("Custom OpenAI-compatible endpoint", "custom"),
                ],
            )
        )
    )
    model_id, secret_name = PROVIDER_DEFAULTS[provider]
    api_base = None
    bedrock_region = "eu-central-1"
    if provider == LLMProvider.BEDROCK:
        bedrock_region = str(
            ask(
                questionary.select(
                    "Bedrock region",
                    choices=["eu-central-1", "us-east-1", "us-east-2", "us-west-2"],
                )
            )
        )
    elif provider == LLMProvider.CUSTOM:
        model_id = str(ask(questionary.text("Model alias", default="custom-model"))).strip()
        api_base = str(ask(questionary.text("OpenAI-compatible API base URL"))).strip()

    secret = str(ask(questionary.password(f"{secret_name} (required)"))).strip()
    if not secret:
        raise RuntimeError(f"{secret_name} is required")
    groot = bool(ask(questionary.confirm("Enable Groot behavior-tree windows?", default=has_display())))
    viz_port = int(str(ask(questionary.text("haru-viz host port", default="5173"))))
    rosbridge_port = int(
        str(ask(questionary.text("ROS bridge base host port (uses four ports)", default="9090")))
    )
    llm_port = int(str(ask(questionary.text("LiteLLM host port", default="4050"))))
    ipad = bool(ask(questionary.confirm("Launch the optional iPad stack?", default=False)))
    projector = bool(ask(questionary.confirm("Launch the optional projector stack?", default=False)))
    timeline_compatibility = bool(
        ask(
            questionary.confirm(
                "Start the local timeline compatibility server if the robot does not provide one?",
                default=deployment == Deployment.SIMULATOR,
            )
        )
    )
    launch = bool(ask(questionary.confirm("Launch the configured deployment after setup?", default=True)))
    answers = SetupAnswers(
        deployment=deployment,
        robot_host=robot_host,
        llm_provider=provider,
        llm_model_id=model_id,
        llm_api_base=api_base,
        bedrock_region=bedrock_region,
        zoom_h8_enabled=zoom,
        kinect_enabled=kinect,
        kinect_transcription_enabled=kinect_speech,
        groot_enabled=groot,
        viz_port=viz_port,
        rosbridge_port=rosbridge_port,
        llm_port=llm_port,
        gpu_available=gpu,
        ipad_enabled=ipad,
        projector_enabled=projector,
        timeline_compatibility_enabled=timeline_compatibility,
        launch_after_setup=launch,
    )
    occupied = [
        port
        for port in (
            answers.viz_port,
            answers.rosbridge_port,
            answers.rosbridge_port + 1,
            answers.rosbridge_port + 2,
            answers.rosbridge_port + 3,
            answers.llm_port,
            answers.nlp_port,
            answers.memory_http_port,
            answers.memory_grpc_port,
            answers.cerevoice_port,
            answers.gpt_sovits_port,
            answers.tts_api_port,
        )
        if not port_available(port)
    ]
    if occupied:
        proceed = ask(
            questionary.confirm(
                f"Host ports already in use: {', '.join(map(str, occupied))}. Save anyway?",
                default=False,
            )
        )
        if not proceed:
            raise typer.Abort()
    return answers, secret


def answers_from_file(path: Path) -> tuple[SetupAnswers, str | None]:
    yaml = YAML(typ="safe")
    with path.open(encoding="utf-8") as stream:
        answers = SetupAnswers.model_validate(yaml.load(stream))
    return answers, os.environ.get(answers.secret_name)


@app.command()
def setup(
    answers: Path | None = typer.Option(None, exists=True, dir_okay=False, help="Non-interactive answers YAML."),
    dry_run: bool = typer.Option(False, help="Write and validate configuration without pulls or launch."),
    refresh_data: bool = typer.Option(False, help="Replace downloaded data bundles before configuring."),
) -> None:
    """Run the guided, idempotent new-host bootstrap."""
    root = repo_root()
    selected, secret = answers_from_file(answers) if answers else interactive_answers()
    if not secret and not has_provider_secret(root, selected):
        raise RuntimeError(
            f"{selected.secret_name} is required; export it when using --answers or rerun interactively"
        )
    orchestrator = Orchestrator(root)
    if refresh_data:
        orchestrator.refresh_data()
    elif not data_is_present(root):
        if answers or bool(ask(questionary.confirm("Download only the missing data bundles now?", default=True))):
            orchestrator.download_missing_data()
    ConfigurationWriter(root).write(selected, secret)
    console.print(f"[green]Configuration written to {root / '.haru'}[/green]")
    orchestrator.validate()
    if dry_run:
        return
    if answers or bool(ask(questionary.confirm("Pull deployment images now?", default=True))):
        orchestrator.pull()
    if selected.launch_after_setup:
        orchestrator.up()
        console.print("[green]Deployment is running.[/green]")
        if not answers and bool(ask(questionary.confirm("Run a minimal live LLM smoke test?", default=False))):
            _llm_smoke(selected.llm_port)
        doctor()


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json", help="Emit machine-readable results.")) -> None:
    """Inspect local configuration and live deployment health."""
    root = repo_root()
    checks = Orchestrator(root).checks()
    if json_output:
        import json

        console.print_json(data=[check.__dict__ for check in checks])
        raise typer.Exit(0 if all(check.ok for check in checks) else 1)
    table = Table("Check", "Status", "Details")
    for check in checks:
        table.add_row(check.name, "[green]OK[/green]" if check.ok else "[red]FAIL[/red]", check.details)
    console.print(table)
    raise typer.Exit(0 if all(check.ok for check in checks) else 1)


@app.command()
def up() -> None:
    """Start the configured deployment in dependency order."""
    Orchestrator(repo_root()).up()


@app.command()
def down(
    cleanup: bool = typer.Option(False, help="Also run Docker system prune after confirmation."),
) -> None:
    """Cancel active work and stop only Haru Compose projects."""
    root = repo_root()
    ScenarioManager(root).stop(quiet=True)
    orchestrator = Orchestrator(root)
    orchestrator.down()
    if cleanup and bool(ask(questionary.confirm("Prune unused Docker data on this host?", default=False))):
        orchestrator.clean_docker()


@scenario_app.command("run")
def run_scenario(
    path: Path = typer.Argument(DEFAULT_SCENARIO),
    continue_session: bool = typer.Option(False, help="Retain LLM and context state from the previous run."),
) -> None:
    """Run a fresh-ID scenario and stream its result."""
    success = ScenarioManager(repo_root()).run(path, continue_session=continue_session)
    raise typer.Exit(0 if success else 1)


@scenario_app.command("stop")
def stop_scenario() -> None:
    """Cancel the current scenario and force robot tracking off."""
    ScenarioManager(repo_root()).stop()


@app.command()
def logs() -> None:
    """Capture a bounded log bundle for the last scenario."""
    path = ScenarioManager(repo_root()).capture_logs()
    console.print(f"[green]Logs captured at {path}[/green]")


def _llm_smoke(port: int) -> None:
    payload = b'{"model":"haru:canonical","messages":[{"role":"user","content":"Reply OK"}],"max_tokens":4}'
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 200:
            raise RuntimeError(f"LLM smoke test returned HTTP {response.status}")
    console.print("[green]LLM smoke test passed.[/green]")


def main() -> None:
    try:
        app()
    except (RuntimeError, FileNotFoundError, ValidationError) as error:
        console.print(f"[red]Error:[/red] {error}", file=sys.stderr)
        raise typer.Exit(1) from error


if __name__ == "__main__":
    main()
