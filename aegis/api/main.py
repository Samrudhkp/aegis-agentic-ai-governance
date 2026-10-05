"""FastAPI service exposing evaluation and governance endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from aegis import __version__
from aegis.adversarial.suite import AdversarialSuite
from aegis.config import get_settings
from aegis.evaluation.engine import EvaluationEngine
from aegis.governance.gates import apply_human_decision
from aegis.observability.logging import configure_logging
from aegis.observability.telemetry import init_telemetry

configure_logging()
init_telemetry()

app = FastAPI(
    title="Aegis Agentic AI Governance",
    description=(
        "Evaluate agent task completion, quality, tool usage, safety, and trajectories. "
        "Apply risk-based deployment gates before Cloud Run releases."
    ),
    version=__version__,
)


class EvalRequest(BaseModel):
    dataset: str = "smoke"
    include_adversarial: bool = False
    persist: bool = True


class ApprovalRequest(BaseModel):
    run_id: str
    approved: bool
    reviewer: str = Field(min_length=1)


# In-memory store for demo / local approval workflow
_RUNS: dict[str, Any] = {}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "version": __version__, "mode": settings.mode}


@app.post("/v1/evaluations")
def run_evaluation(body: EvalRequest) -> dict[str, Any]:
    engine = EvaluationEngine()
    run = engine.run(
        dataset=body.dataset,
        include_adversarial=body.include_adversarial,
        persist=body.persist,
    )
    _RUNS[run.run_id] = run
    return run.model_dump(mode="json")


@app.post("/v1/adversarial")
def run_adversarial() -> dict[str, Any]:
    suite = AdversarialSuite()
    run = suite.run(persist=True)
    _RUNS[run.run_id] = run
    return suite.summary(run)


@app.get("/v1/evaluations/{run_id}")
def get_evaluation(run_id: str) -> dict[str, Any]:
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run.model_dump(mode="json")


@app.get("/v1/gates/{run_id}")
def get_gate_decision(run_id: str) -> dict[str, Any]:
    run = _RUNS.get(run_id)
    if not run or not run.governance:
        raise HTTPException(status_code=404, detail="gate decision not found")
    return run.governance.model_dump(mode="json")


@app.post("/v1/approvals")
def submit_approval(body: ApprovalRequest) -> dict[str, Any]:
    run = _RUNS.get(body.run_id)
    if not run or not run.governance:
        raise HTTPException(status_code=404, detail="run not found")
    result = apply_human_decision(run.governance, body.approved, body.reviewer)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


def create_app() -> FastAPI:
    return app
