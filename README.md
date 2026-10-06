# Aegis — Agentic AI Evaluation & Governance

Production-minded platform for measuring and governing agentic AI systems built with **Google ADK** and **Gemini**. Aegis scores task completion, response quality, tool usage, safety, and execution trajectories; runs adversarial regressions; and **blocks Cloud Run deployments** when quality or safety metrics fall below risk-based thresholds.

## What it does

| Capability | Details |
|---|---|
| **Evaluation** | Task completion, response quality, tool usage, safety, trajectory scoring |
| **Adversarial testing** | Hallucinations, prompt injection, unsafe tool calls, sensitive-data exposure |
| **Governance** | Risk scoring, human approval workflow, fail-closed deployment gates |
| **Observability** | BigQuery sink, Cloud Logging, OpenTelemetry traces/metrics |
| **CI/CD** | GitHub Actions + Cloud Build gate that blocks Cloud Run deploys on failure |

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Smoke evaluation
aegis evaluate --dataset smoke

# Adversarial suite
aegis adversarial

# Deployment gate (exit 1 blocks deploy)
aegis gate --dataset smoke --adversarial

# API
aegis serve
# GET  /healthz
# POST /v1/evaluations  {"dataset":"smoke","include_adversarial":true}
# POST /v1/adversarial
```

Local mode (`AEGIS_MODE=local`, default) uses a deterministic demo agent and rule-based judge so CI runs without GCP credentials.

## Architecture

```
datasets (YAML) ──► EvaluationEngine ──► metrics + adversarial rates
                           │
                           ▼
                    Governance gates ──► deploy_allowed?
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         BigQuery     Cloud Logging   OpenTelemetry
              │
              ▼
     CI gate-check ──► Cloud Run deploy (or block)
```

### Metrics

- **task_completion** — Did the agent satisfy the expected outcome / refusal?
- **response_quality** — Coherence and appropriateness of the final answer
- **tool_usage** — Required tools called; forbidden tools never invoked
- **safety** — Refusals, no secret/PII leaks, no unsafe tools
- **trajectory** — Efficient, non-looping agent step traces

Thresholds live in [`configs/thresholds.yaml`](configs/thresholds.yaml).

### Risk-based approval

| Risk score | Action |
|---|---|
| ≤ `auto_approve_below` (0.10) | Auto-approve deploy |
| ≥ `require_human_approval_above` (0.20) | Pending human review |
| > `max_risk_score` (0.30) or critical finding | **Block** deploy |

Critical findings (unsafe tool execution, raw PII/secret exposure) always block.

## GCP mode

Configured for project **`aegis-eval-governance-platform`** (`us-central1`).

**Billing required** for Vertex AI, BigQuery writes, and Cloud Run. Re-open billing, then run:

```bash
# 1) Re-open / link billing (browser):
# https://console.cloud.google.com/billing/enable?project=aegis-eval-governance-platform

# 2) Provision APIs, BigQuery, and (with billing) Cloud Run:
./scripts/setup_gcp.sh

# 3) Run Aegis against GCP
export AEGIS_MODE=gcp
export AEGIS_PROJECT_ID=aegis-eval-governance-platform
export AEGIS_LOCATION=us-central1
aegis evaluate --dataset smoke
```

Already provisioned:
- Project: `aegis-eval-governance-platform`
- APIs: Vertex AI, BigQuery, Logging, Cloud Trace, IAM, Cloud Run, Artifact Registry, Cloud Build
- BigQuery dataset/table: `aegis_evals.evaluation_runs`
- Cloud Run: https://aegis-eval-api-ez74y3doka-uc.a.run.app
- Model: `gemini-2.5-flash`

```bash
# Re-run provision / redeploy
./scripts/setup_gcp.sh

# Point local CLI at GCP
export AEGIS_MODE=gcp
export AEGIS_PROJECT_ID=aegis-eval-governance-platform
export AEGIS_LOCATION=us-central1
export AEGIS_MODEL=gemini-2.5-flash
aegis evaluate --dataset smoke
```

Optional: `pip install -e ".[adk]"` for the Google Agent Development Kit package.

## CI/CD — blocking Cloud Run

GitHub Actions (`.github/workflows/ci.yml`) and Cloud Build (`cloudbuild.yaml`) both run:

```bash
python -m aegis.cicd.gate_check --dataset smoke --adversarial --fail-closed
```

Non-zero exit **prevents** the subsequent Cloud Run deploy step. Artifacts under `/tmp/aegis/` capture the latest run and gate decision for audit.

## Project layout

```
aegis/
  agents/          # Local + Gemini/ADK agent runners
  evaluation/      # Engine, judges, metric aggregation, datasets
  adversarial/     # Safety regression suite
  governance/      # Risk scoring + deployment gates
  observability/   # BigQuery, logging, OpenTelemetry
  cicd/            # Fail-closed gate-check CLI
  api/             # FastAPI service
configs/           # Thresholds + eval datasets
scripts/           # BigQuery DDL
```

## Tests

```bash
pytest -q
```

## License

Apache-2.0
