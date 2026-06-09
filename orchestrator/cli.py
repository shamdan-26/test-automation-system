from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.version_option("1.0.0", prog_name="tas")
def main() -> None:
    """Test Automation System — run tests, generate cases, submit bugs."""


@main.command()
def setup() -> None:
    """Interactive setup wizard — configure connections, engines, and output paths."""
    from orchestrator.setup_wizard import run_setup_wizard
    run_setup_wizard()


@main.command()
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), required=True, help="Path to tas_config.yml")
@click.option("--input", "-i", "inputs", type=click.Path(exists=True, path_type=Path), multiple=True, help="Input files (documents, stories, tasks). Repeatable.")
@click.option("--engine", "-e", "engines", multiple=True, help="Run only specific engines: api_rest, api_soap, ui, mobile, performance, regression")
@click.option("--triggered-by", default="manual", show_default=True, help="Trigger source recorded in report")
def run(config: Path, inputs: tuple[Path, ...], engines: tuple[str, ...], triggered_by: str) -> None:
    """Run the full test pipeline against a configured environment."""
    from orchestrator.runner import load_config, run as _run
    from utils.logger import setup_logging

    cfg = load_config(config)
    setup_logging(level=cfg.get("system", {}).get("log_level", "INFO"))

    if not inputs:
        console.print("[yellow]No input files provided. Running with pre-generated test cases if available.[/yellow]")

    console.rule("[bold cyan]Test Automation System")
    summary = _run(
        config=cfg,
        input_paths=list(inputs),
        engines_override=list(engines) or None,
        triggered_by=triggered_by,
    )

    _print_summary(summary)
    raise SystemExit(0 if summary.overall_status.value == "passed" else 1)


@main.command()
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--input", "-i", "inputs", type=click.Path(exists=True, path_type=Path), multiple=True)
def generate(config: Path, inputs: tuple[Path, ...]) -> None:
    """Parse input files and generate test case YAML files only (no execution)."""
    from input_parser.task_parser import ParserRegistry
    from test_generator.generator import TestCaseGenerator

    cfg = _load(config)
    output_dir = Path(cfg["system"]["output_dir"]) / "test_cases"
    registry = ParserRegistry()
    parsed = []
    for path in inputs:
        parsed.extend(registry.parse(path))

    cases = TestCaseGenerator(output_dir).generate(parsed)
    console.print(f"[green]Generated {len(cases)} test case(s) in {output_dir}[/green]")


@main.command()
@click.argument("config_path", type=click.Path(path_type=Path))
def show_config(config_path: Path) -> None:
    """Print the resolved config from a tas_config.yml file."""
    cfg = _load(config_path)
    console.print_json(data=cfg)


def _load(config_path: Path) -> dict[str, Any]:
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def _print_summary(summary: Any) -> None:
    console.rule()
    status_color = "green" if summary.overall_status.value == "passed" else "red"
    console.print(f"\nOverall: [{status_color} bold]{summary.overall_status.value.upper()}[/{status_color} bold]")
    console.print(f"Run ID : {summary.run_id}")
    console.print(f"Branch : {summary.git_branch} ({summary.git_commit[:7] or 'N/A'})")
    console.print(f"Bugs   : {summary.bugs_submitted} submitted\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Engine", style="cyan", no_wrap=True)
    table.add_column("Total", justify="right")
    table.add_column("Passed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Pass Rate", justify="right")
    table.add_column("Duration", justify="right")

    for report in summary.engine_reports:
        table.add_row(
            report.engine,
            str(report.total),
            str(report.passed),
            str(report.failed),
            f"{report.pass_rate:.1f}%",
            f"{report.duration_s:.1f}s",
        )

    console.print(table)

    for key, path in summary.report_paths.items():
        console.print(f"[dim]{key.upper()} report:[/dim] {path}")
