"""Aegis CLI — evaluate, adversarial test, and gate-check."""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console
from rich.table import Table

from aegis import __version__
from aegis.adversarial.suite import AdversarialSuite
from aegis.config import get_settings
from aegis.evaluation.engine import EvaluationEngine
from aegis.observability.logging import configure_logging

console = Console()


@click.group()
@click.version_option(__version__, prog_name="aegis")
def main() -> None:
    """Aegis — agentic AI evaluation and governance."""
    configure_logging()


@main.command("evaluate")
@click.option("--dataset", default="smoke", show_default=True)
@click.option("--adversarial/--no-adversarial", default=False)
@click.option("--json-out", "json_out", is_flag=True, help="Print full JSON result")
def evaluate_cmd(dataset: str, adversarial: bool, json_out: bool) -> None:
    """Run an evaluation dataset and print aggregate metrics."""
    engine = EvaluationEngine()
    run = engine.run(dataset=dataset, include_adversarial=adversarial, persist=True)
    if json_out:
        click.echo(json.dumps(run.model_dump(mode="json"), indent=2))
        return
    table = Table(title=f"Evaluation {run.run_id[:8]} — {run.dataset}")
    table.add_column("Metric")
    table.add_column("Score", justify="right")
    for k, v in run.metrics.as_dict().items():
        table.add_row(k, f"{v:.3f}")
    console.print(table)
    if run.governance:
        console.print(run.governance.summary)


@main.command("adversarial")
@click.option("--json-out", "json_out", is_flag=True)
def adversarial_cmd(json_out: bool) -> None:
    """Run adversarial regression suite."""
    suite = AdversarialSuite()
    run = suite.run(persist=True)
    summary = suite.summary(run)
    if json_out:
        click.echo(json.dumps(summary, indent=2))
        return
    console.print(summary)


@main.command("gate")
@click.option("--dataset", default="smoke", show_default=True)
@click.option("--adversarial/--no-adversarial", default=True)
@click.option("--fail-closed/--fail-open", default=True)
def gate_cmd(dataset: str, adversarial: bool, fail_closed: bool) -> None:
    """Run deployment gate check (blocks Cloud Run on failure)."""
    from aegis.cicd.gate_check import gate_check

    # Invoke click command programmatically
    try:
        gate_check.main(
            args=[
                "--dataset",
                dataset,
                "--adversarial" if adversarial else "--no-adversarial",
                "--fail-closed" if fail_closed else "--fail-open",
            ],
            standalone_mode=False,
        )
    except SystemExit as exc:
        sys.exit(exc.code or 0)


@main.command("serve")
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def serve_cmd(host: str | None, port: int | None) -> None:
    """Start the Aegis evaluation API."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "aegis.api.main:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
