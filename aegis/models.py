"""Shared Pydantic models for evaluation, governance, and observability."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MetricName(str, Enum):
    TASK_COMPLETION = "task_completion"
    RESPONSE_QUALITY = "response_quality"
    TOOL_USAGE = "tool_usage"
    SAFETY = "safety"
    TRAJECTORY = "trajectory"


class AttackType(str, Enum):
    HALLUCINATION = "hallucination"
    PROMPT_INJECTION = "prompt_injection"
    UNSAFE_TOOL_CALL = "unsafe_tool_call"
    SENSITIVE_DATA_EXPOSURE = "sensitive_data_exposure"
    NONE = "none"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalDecision(str, Enum):
    AUTO_APPROVED = "auto_approved"
    PENDING_HUMAN = "pending_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    allowed: bool = True
    blocked_reason: str | None = None


class AgentStep(BaseModel):
    """One step in an agent execution trajectory."""

    step_index: int
    role: str  # system | user | assistant | tool
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    latency_ms: float = 0.0


class AgentTrajectory(BaseModel):
    case_id: str
    steps: list[AgentStep] = Field(default_factory=list)
    final_response: str = ""
    total_latency_ms: float = 0.0
    error: str | None = None

    @property
    def tool_names(self) -> list[str]:
        names: list[str] = []
        for step in self.steps:
            for tc in step.tool_calls:
                names.append(tc.name)
        return names


class ExpectedBehavior(BaseModel):
    answer_contains: str | None = None
    must_call_tools: list[str] = Field(default_factory=list)
    must_not_call_tools: list[str] | bool = False
    tool_args_contains: dict[str, dict[str, Any]] = Field(default_factory=dict)
    must_refuse: bool = False
    must_not_fabricate_citation: bool = False
    must_not_leak_system_prompt: bool = False
    must_not_leak_secrets: bool = False
    must_not_expose_pii: list[str] = Field(default_factory=list)
    must_refuse_or_redact: bool = False
    allowed_behaviors: list[str] = Field(default_factory=list)


class EvalCase(BaseModel):
    id: str
    category: str
    prompt: str
    expected: ExpectedBehavior = Field(default_factory=ExpectedBehavior)
    rubrics: dict[str, str] = Field(default_factory=dict)
    attack_type: AttackType = AttackType.NONE


class MetricScore(BaseModel):
    name: MetricName
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    rationale: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class CaseResult(BaseModel):
    case_id: str
    category: str
    attack_type: AttackType = AttackType.NONE
    trajectory: AgentTrajectory
    metrics: list[MetricScore] = Field(default_factory=list)
    adversarial_passed: bool | None = None
    findings: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class AggregateMetrics(BaseModel):
    task_completion: float = 0.0
    response_quality: float = 0.0
    tool_usage: float = 0.0
    safety: float = 0.0
    trajectory: float = 0.0
    overall: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "task_completion": self.task_completion,
            "response_quality": self.response_quality,
            "tool_usage": self.tool_usage,
            "safety": self.safety,
            "trajectory": self.trajectory,
            "overall": self.overall,
        }


class AdversarialRates(BaseModel):
    hallucination_pass_rate: float = 1.0
    prompt_injection_pass_rate: float = 1.0
    unsafe_tool_call_pass_rate: float = 1.0
    sensitive_data_pass_rate: float = 1.0


class GateFailure(BaseModel):
    gate: str
    actual: float | str | bool
    threshold: float | str | bool
    message: str


class GovernanceDecision(BaseModel):
    risk_score: float
    risk_level: RiskLevel
    approval: ApprovalDecision
    failures: list[GateFailure] = Field(default_factory=list)
    critical_findings: list[str] = Field(default_factory=list)
    deploy_allowed: bool = False
    requires_human_approval: bool = False
    summary: str = ""


class EvaluationRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=utcnow)
    dataset: str
    agent_name: str
    agent_version: str = "local"
    mode: str = "local"
    case_results: list[CaseResult] = Field(default_factory=list)
    metrics: AggregateMetrics = Field(default_factory=AggregateMetrics)
    adversarial: AdversarialRates = Field(default_factory=AdversarialRates)
    governance: GovernanceDecision | None = None
    total_latency_ms: float = 0.0
    failures: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ThresholdConfig(BaseModel):
    metrics: dict[str, dict[str, float]]
    adversarial: dict[str, float]
    governance: dict[str, Any]
    deployment: dict[str, Any] = Field(default_factory=dict)
    environment: str = "production"
    version: str = "1.0"
