"""Evaluation result sinks — local JSONL and BigQuery."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

from aegis.config import Settings, get_settings
from aegis.models import EvaluationRun
from aegis.observability.logging import log_evaluation

_LOG = logging.getLogger("aegis.sinks")
ARTIFACTS = Path("/tmp/aegis") if Path("/tmp").exists() else Path.cwd() / ".aegis"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


class EvaluationSink(Protocol):
    def write(self, run: EvaluationRun) -> None: ...


class LocalJsonlSink:
    """Writes evaluation runs to a local JSONL file for CI artifacts."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (ARTIFACTS / "evaluation_runs.jsonl")

    def write(self, run: EvaluationRun) -> None:
        payload = run.model_dump(mode="json")
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
        # Also write latest summary for gate checks
        summary_path = ARTIFACTS / "latest_run.json"
        summary_path.write_text(json.dumps(payload, indent=2))
        log_evaluation(
            {
                "run_id": run.run_id,
                "dataset": run.dataset,
                "overall": run.metrics.overall,
                "deploy_allowed": bool(run.governance and run.governance.deploy_allowed),
                "risk_score": run.governance.risk_score if run.governance else None,
                "latency_ms": run.total_latency_ms,
                "failures": run.failures,
            }
        )
        _LOG.info("Wrote evaluation run %s to %s", run.run_id, self.path)


class BigQuerySink:
    """Persists evaluation runs to BigQuery for production observability."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._local = LocalJsonlSink()

    def write(self, run: EvaluationRun) -> None:
        # Always keep a local copy.
        self._local.write(run)
        try:
            from google.cloud import bigquery
        except ImportError:  # pragma: no cover
            _LOG.warning("google-cloud-bigquery not available; local sink only")
            return

        client = bigquery.Client(project=self.settings.project_id)
        table_id = (
            f"{self.settings.project_id}."
            f"{self.settings.bigquery_dataset}."
            f"{self.settings.bigquery_table}"
        )
        row = {
            "run_id": run.run_id,
            "created_at": run.created_at.isoformat(),
            "dataset": run.dataset,
            "agent_name": run.agent_name,
            "agent_version": run.agent_version,
            "mode": run.mode,
            "task_completion": run.metrics.task_completion,
            "response_quality": run.metrics.response_quality,
            "tool_usage": run.metrics.tool_usage,
            "safety": run.metrics.safety,
            "trajectory": run.metrics.trajectory,
            "overall": run.metrics.overall,
            "risk_score": run.governance.risk_score if run.governance else None,
            "deploy_allowed": run.governance.deploy_allowed if run.governance else None,
            "latency_ms": run.total_latency_ms,
            "failures": run.failures,
            "payload": json.dumps(run.model_dump(mode="json")),
        }
        errors = client.insert_rows_json(table_id, [row])
        if errors:  # pragma: no cover
            _LOG.error("BigQuery insert errors: %s", errors)
        else:
            _LOG.info("Inserted evaluation run into %s", table_id)


class CompositeSink:
    def __init__(self, sinks: list[EvaluationSink]) -> None:
        self.sinks = sinks

    def write(self, run: EvaluationRun) -> None:
        for sink in self.sinks:
            sink.write(run)


def build_sink(settings: Settings | None = None) -> EvaluationSink:
    settings = settings or get_settings()
    if settings.mode == "gcp":
        return BigQuerySink(settings)
    return LocalJsonlSink()
