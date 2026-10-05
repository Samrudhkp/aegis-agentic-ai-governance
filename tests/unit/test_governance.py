"""Tests for governance gates and risk scoring."""

from pathlib import Path

from aegis.governance.gates import evaluate_gates, risk_level_for
from aegis.models import (
    AdversarialRates,
    AggregateMetrics,
    ApprovalDecision,
    EvaluationRun,
    RiskLevel,
)

THRESHOLDS = Path(__file__).resolve().parents[2] / "configs" / "thresholds.yaml"


def _run(
    metrics: AggregateMetrics | None = None,
    adversarial: AdversarialRates | None = None,
) -> EvaluationRun:
    return EvaluationRun(
        dataset="test",
        agent_name="test",
        metrics=metrics
        or AggregateMetrics(
            task_completion=0.95,
            response_quality=0.9,
            tool_usage=0.9,
            safety=0.99,
            trajectory=0.9,
            overall=0.93,
        ),
        adversarial=adversarial or AdversarialRates(),
    )


def test_risk_levels():
    assert risk_level_for(0.05) == RiskLevel.LOW
    assert risk_level_for(0.2) == RiskLevel.MEDIUM
    assert risk_level_for(0.4) == RiskLevel.HIGH
    assert risk_level_for(0.8) == RiskLevel.CRITICAL


def test_gates_pass_on_healthy_run():
    decision = evaluate_gates(_run(), THRESHOLDS)
    assert decision.deploy_allowed is True
    assert decision.approval == ApprovalDecision.AUTO_APPROVED
    assert decision.risk_level == RiskLevel.LOW


def test_gates_block_low_safety():
    run = _run(
        metrics=AggregateMetrics(
            task_completion=0.95,
            response_quality=0.9,
            tool_usage=0.9,
            safety=0.50,
            trajectory=0.9,
            overall=0.7,
        )
    )
    decision = evaluate_gates(run, THRESHOLDS)
    assert decision.deploy_allowed is False
    assert decision.approval == ApprovalDecision.BLOCKED
    assert any(f.gate == "metric.safety" for f in decision.failures)


def test_gates_block_adversarial_failure():
    run = _run(
        adversarial=AdversarialRates(
            unsafe_tool_call_pass_rate=0.5,
            sensitive_data_pass_rate=1.0,
        )
    )
    decision = evaluate_gates(run, THRESHOLDS)
    assert decision.deploy_allowed is False
    assert any("unsafe_tool_call" in f.gate for f in decision.failures)
