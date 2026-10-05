"""Core evaluation engine."""

from __future__ import annotations

import time
from typing import Iterable

from aegis.agents.runner import AgentRunner, build_agent
from aegis.config import Settings, get_settings
from aegis.evaluation.datasets import load_dataset
from aegis.evaluation.judges import GeminiJudge, LocalJudge
from aegis.evaluation.metrics import adversarial_pass_rates, average_metrics
from aegis.governance.gates import evaluate_gates
from aegis.models import AttackType, CaseResult, EvalCase, EvaluationRun, MetricName
from aegis.observability.telemetry import get_tracer, record_eval_metrics
from aegis.observability.sinks import EvaluationSink, build_sink


class EvaluationEngine:
    """Runs eval datasets against an agent, scores metrics, and applies gates."""

    def __init__(
        self,
        settings: Settings | None = None,
        agent: AgentRunner | None = None,
        sink: EvaluationSink | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.agent = agent or build_agent(self.settings)
        self.judge = (
            LocalJudge() if self.settings.mode == "local" else GeminiJudge(self.settings)
        )
        self.sink = sink or build_sink(self.settings)
        self.tracer = get_tracer()

    def run(
        self,
        dataset: str = "smoke",
        include_adversarial: bool = False,
        persist: bool = True,
    ) -> EvaluationRun:
        cases = list(load_dataset(dataset))
        if include_adversarial and dataset != "adversarial":
            cases.extend(load_dataset("adversarial"))

        with self.tracer.start_as_current_span("aegis.evaluation.run") as span:
            span.set_attribute("aegis.dataset", dataset)
            span.set_attribute("aegis.agent", getattr(self.agent, "name", "unknown"))
            started = time.perf_counter()
            case_results = [self._evaluate_case(case) for case in cases]
            elapsed = (time.perf_counter() - started) * 1000

            metrics = average_metrics(case_results)
            adversarial = adversarial_pass_rates(case_results)
            run = EvaluationRun(
                dataset=dataset if not include_adversarial else f"{dataset}+adversarial",
                agent_name=getattr(self.agent, "name", "unknown"),
                agent_version=getattr(self.agent, "version", "unknown"),
                mode=self.settings.mode,
                case_results=case_results,
                metrics=metrics,
                adversarial=adversarial,
                total_latency_ms=elapsed,
                failures=sum(1 for c in case_results if any(not m.passed for m in c.metrics)),
            )
            run.governance = evaluate_gates(run, self.settings.thresholds_path)
            record_eval_metrics(run)
            if persist:
                self.sink.write(run)
            return run

    def run_cases(self, cases: Iterable[EvalCase], dataset: str = "custom") -> EvaluationRun:
        case_results = [self._evaluate_case(case) for case in cases]
        run = EvaluationRun(
            dataset=dataset,
            agent_name=getattr(self.agent, "name", "unknown"),
            agent_version=getattr(self.agent, "version", "unknown"),
            mode=self.settings.mode,
            case_results=case_results,
            metrics=average_metrics(case_results),
            adversarial=adversarial_pass_rates(case_results),
            total_latency_ms=sum(c.latency_ms for c in case_results),
        )
        run.governance = evaluate_gates(run, self.settings.thresholds_path)
        return run

    def _evaluate_case(self, case: EvalCase) -> CaseResult:
        with self.tracer.start_as_current_span("aegis.evaluation.case") as span:
            span.set_attribute("aegis.case_id", case.id)
            span.set_attribute("aegis.category", case.category)
            started = time.perf_counter()
            trajectory = self.agent.run(case.id, case.prompt)
            metrics = self.judge.score_case(case, trajectory)
            findings: list[str] = []
            for metric in metrics:
                if not metric.passed:
                    findings.append(f"{metric.name.value}: {metric.rationale}")

            adv_passed = None
            if case.attack_type != AttackType.NONE:
                safety = next((m for m in metrics if m.name == MetricName.SAFETY), None)
                tool = next((m for m in metrics if m.name == MetricName.TOOL_USAGE), None)
                adv_passed = bool(safety and safety.passed and tool and tool.passed)

            elapsed = (time.perf_counter() - started) * 1000
            return CaseResult(
                case_id=case.id,
                category=case.category,
                attack_type=case.attack_type,
                trajectory=trajectory,
                metrics=metrics,
                adversarial_passed=adv_passed,
                findings=findings,
                latency_ms=elapsed,
            )
