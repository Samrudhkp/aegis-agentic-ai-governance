"""CI/CD deployment gate — exit non-zero to block Cloud Run deploys."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from aegis.adversarial.suite import AdversarialSuite
from aegis.config import get_settings
from aegis.evaluation.engine import EvaluationEngine
from aegis.observability.logging import configure_logging
from aegis.observability.sinks import ARTIFACTS

console = Console()


def _print_gate_report(run) -> None:
    gov = run.governance
    table = Table(title="Aegis Deployment Gate")
    table.add_column("Metric")
    table.add_column("Score", justify="right")
    metrics = run.metrics.as_dict()
    for name, value in metrics.items():
        table.add_row(name, f"{value:.3f}")
    console.print(table)

    if gov:
        console.print(f"[bold]Risk:[/bold] {gov.risk_score:.3f} ({gov.risk_level.value})")
        console.print(f"[bold]Approval:[/bold] {gov.approval.value}")
        console.print(f"[bold]Deploy allowed:[/bold] {gov.deploy_allowed}")
        if gov.failures:
            console.print("[red]Gate failures:[/red]")
            for failure in gov.failures:
                console.print(f"  - {failure.message}")
        if gov.critical_findings:
            console.print("[red]Critical findings:[/red]")
            for finding in gov.critical_findings:
                console.print(f"  - {finding}")


@click.command("gate-check")
@click.option("--dataset", default="smoke", show_default=True)
@click.option("--adversarial/--no-adversarial", default=True, show_default=True)
@click.option(
    "--fail-closed/--fail-open",
    default=True,
    show_default=True,
    help="Exit non-zero when gates fail (blocks Cloud Run deploy).",
)
@click.option(
    "--from-artifact",
    type=click.Path(path_type=Path),
    default=None,
    help="Evaluate an existing latest_run.json instead of re-running.",
)
def gate_check(
    dataset: str,
    adversarial: bool,
    fail_closed: bool,
    from_artifact: Path | None,
) -> None:
    """Run evaluations and block deployment when quality/safety gates fail."""
    configure_logging()
    settings = get_settings()

    if from_artifact:
        payload = json.loads(from_artifact.read_text())
        from aegis.models import EvaluationRun
        from aegis.governance.gates import evaluate_gates

        run = EvaluationRun.model_validate(payload)
        run.governance = evaluate_gates(run, settings.thresholds_path)
    else:
        engine = EvaluationEngine(settings=settings)
        run = engine.run(dataset=dataset, include_adversarial=adversarial, persist=True)
        if adversarial and dataset != "adversarial":
            # Ensure adversarial rates are populated even if dataset already mixed
            pass

    _print_gate_report(run)
    artifact = ARTIFACTS / "gate_result.json"
    artifact.write_text(
        json.dumps(
            {
                "run_id": run.run_id,
                "deploy_allowed": bool(run.governance and run.governance.deploy_allowed),
                "governance": run.governance.model_dump(mode="json") if run.governance else None,
                "metrics": run.metrics.as_dict(),
                "adversarial": run.adversarial.model_dump(),
            },
            indent=2,
        )
    )
    console.print(f"Wrote gate artifact to {artifact}")

    allowed = bool(run.governance and run.governance.deploy_allowed)
    if allowed:
        console.print("[green]PASS — Cloud Run deployment permitted[/green]")
        sys.exit(0)

    console.print("[red]FAIL — Cloud Run deployment blocked[/red]")
    if fail_closed or settings.fail_closed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    gate_check()
