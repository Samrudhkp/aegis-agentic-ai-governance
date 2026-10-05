"""Adversarial and regression testing orchestration."""

from __future__ import annotations

from aegis.evaluation.engine import EvaluationEngine
from aegis.evaluation.datasets import load_dataset
from aegis.models import AttackType, EvaluationRun


ATTACK_CATEGORIES = {
    AttackType.HALLUCINATION,
    AttackType.PROMPT_INJECTION,
    AttackType.UNSAFE_TOOL_CALL,
    AttackType.SENSITIVE_DATA_EXPOSURE,
}


class AdversarialSuite:
    """Automated regression suite for safety-critical failure modes."""

    def __init__(self, engine: EvaluationEngine | None = None) -> None:
        self.engine = engine or EvaluationEngine()

    def run(self, persist: bool = True) -> EvaluationRun:
        cases = load_dataset("adversarial")
        assert all(c.attack_type in ATTACK_CATEGORIES for c in cases)
        run = self.engine.run_cases(cases, dataset="adversarial")
        if persist:
            self.engine.sink.write(run)
        return run

    def summary(self, run: EvaluationRun) -> dict:
        return {
            "run_id": run.run_id,
            "pass_rates": run.adversarial.model_dump(),
            "failures": [
                {
                    "case_id": c.case_id,
                    "attack_type": c.attack_type.value,
                    "findings": c.findings,
                }
                for c in run.case_results
                if c.adversarial_passed is False
            ],
            "governance": run.governance.model_dump() if run.governance else None,
        }
