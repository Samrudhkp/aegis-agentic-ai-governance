"""OpenTelemetry setup for Aegis evaluation spans and metrics."""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from aegis.config import get_settings
from aegis.models import EvaluationRun

_LOG = logging.getLogger("aegis.telemetry")
_INITIALIZED = False


def init_telemetry(service_name: str | None = None) -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    settings = get_settings()
    resource = Resource.create(
        {
            "service.name": service_name or settings.otel_service_name,
            "service.version": "0.1.0",
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    if settings.mode == "gcp":
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            tracer_provider.add_span_processor(
                BatchSpanProcessor(CloudTraceSpanExporter(project_id=settings.project_id))
            )
        except Exception as exc:  # pragma: no cover
            _LOG.warning("Cloud Trace exporter unavailable: %s", exc)

    trace.set_tracer_provider(tracer_provider)
    # Local/CI: in-process meter provider (no console export noise).
    meter_provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(meter_provider)
    _INITIALIZED = True


def get_tracer() -> trace.Tracer:
    if not _INITIALIZED:
        init_telemetry()
    return trace.get_tracer("aegis")


def record_eval_metrics(run: EvaluationRun) -> None:
    if not _INITIALIZED:
        init_telemetry()
    meter = metrics.get_meter("aegis")
    overall = meter.create_histogram("aegis.eval.overall_score")
    latency = meter.create_histogram("aegis.eval.latency_ms")
    failures = meter.create_counter("aegis.eval.failures")
    overall.record(run.metrics.overall, {"dataset": run.dataset, "agent": run.agent_name})
    latency.record(run.total_latency_ms, {"dataset": run.dataset})
    failures.add(run.failures, {"dataset": run.dataset})


def span_attributes_for_run(run: EvaluationRun) -> dict[str, Any]:
    return {
        "aegis.run_id": run.run_id,
        "aegis.dataset": run.dataset,
        "aegis.overall": run.metrics.overall,
        "aegis.deploy_allowed": bool(run.governance and run.governance.deploy_allowed),
    }
