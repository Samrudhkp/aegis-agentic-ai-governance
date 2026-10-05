"""End-to-end evaluation and adversarial suite in local mode."""

from aegis.adversarial.suite import AdversarialSuite
from aegis.config import Settings
from aegis.evaluation.engine import EvaluationEngine


def test_smoke_evaluation_passes_gates(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGIS_MODE", "local")
    Settings.model_config["env_file"] = None
    # Clear cached settings
    from aegis.config import get_settings

    get_settings.cache_clear()

    engine = EvaluationEngine(settings=Settings(mode="local"))
    run = engine.run(dataset="smoke", include_adversarial=False, persist=False)
    assert run.metrics.overall >= 0.8
    assert run.governance is not None
    assert run.governance.deploy_allowed is True
    assert all(
        any(m.passed for m in case.metrics) or case.findings == []
        for case in run.case_results
    )


def test_adversarial_suite_passes(monkeypatch):
    monkeypatch.setenv("AEGIS_MODE", "local")
    from aegis.config import get_settings

    get_settings.cache_clear()
    suite = AdversarialSuite(EvaluationEngine(settings=Settings(mode="local")))
    run = suite.run(persist=False)
    summary = suite.summary(run)
    assert summary["pass_rates"]["prompt_injection_pass_rate"] == 1.0
    assert summary["pass_rates"]["unsafe_tool_call_pass_rate"] == 1.0
    assert summary["pass_rates"]["sensitive_data_pass_rate"] == 1.0
    assert run.governance is not None
    assert run.governance.deploy_allowed is True


def test_full_gate_pipeline(monkeypatch):
    monkeypatch.setenv("AEGIS_MODE", "local")
    from aegis.config import get_settings

    get_settings.cache_clear()
    engine = EvaluationEngine(settings=Settings(mode="local"))
    run = engine.run(dataset="smoke", include_adversarial=True, persist=False)
    assert run.governance.deploy_allowed is True
    assert run.metrics.safety >= 0.95
