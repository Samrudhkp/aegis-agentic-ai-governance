#!/usr/bin/env bash
# Provision Aegis on Google Cloud (project: aegis-eval-governance-platform)
set -euo pipefail

PROJECT="${AEGIS_PROJECT_ID:-aegis-eval-governance-platform}"
REGION="${AEGIS_LOCATION:-us-central1}"
SERVICE="${AEGIS_CLOUD_RUN_SERVICE:-aegis-eval-api}"
IMAGE_REPO="${REGION}-docker.pkg.dev/${PROJECT}/aegis"
IMAGE="${IMAGE_REPO}/aegis-eval-api"

echo "==> Project: ${PROJECT}  Region: ${REGION}"
gcloud config set project "${PROJECT}"

echo "==> Checking billing..."
BILLING_ENABLED=$(gcloud billing projects describe "${PROJECT}" --format='value(billingEnabled)' || echo "false")
if [[ "${BILLING_ENABLED}" != "True" && "${BILLING_ENABLED}" != "true" ]]; then
  echo "WARNING: Billing is not enabled on ${PROJECT}."
  echo "Open https://console.cloud.google.com/billing/linkedaccount?project=${PROJECT}"
  echo "Re-open billing account 01F59D-CE68A5-998B16 (or link an open account), then re-run this script."
fi

echo "==> Enabling APIs..."
APIS=(
  aiplatform.googleapis.com
  bigquery.googleapis.com
  logging.googleapis.com
  cloudtrace.googleapis.com
  iam.googleapis.com
)
# These require active billing:
BILLABLE_APIS=(
  run.googleapis.com
  artifactregistry.googleapis.com
  cloudbuild.googleapis.com
)

gcloud services enable "${APIS[@]}" --project="${PROJECT}"
if [[ "${BILLING_ENABLED}" == "True" || "${BILLING_ENABLED}" == "true" ]]; then
  gcloud services enable "${BILLABLE_APIS[@]}" --project="${PROJECT}"
else
  echo "Skipping Cloud Run / Artifact Registry / Cloud Build until billing is open."
fi

echo "==> Ensuring BigQuery dataset + table..."
bq --location=US mk --dataset --description "Aegis evaluation observability" \
  "${PROJECT}:aegis_evals" 2>/dev/null || true
bq query --use_legacy_sql=false --project_id="${PROJECT}" <<'SQL'
CREATE TABLE IF NOT EXISTS `aegis-eval-governance-platform.aegis_evals.evaluation_runs` (
  run_id STRING NOT NULL,
  created_at TIMESTAMP,
  dataset STRING,
  agent_name STRING,
  agent_version STRING,
  mode STRING,
  task_completion FLOAT64,
  response_quality FLOAT64,
  tool_usage FLOAT64,
  safety FLOAT64,
  trajectory FLOAT64,
  overall FLOAT64,
  risk_score FLOAT64,
  deploy_allowed BOOL,
  latency_ms FLOAT64,
  failures INT64,
  payload JSON
);
SQL

if [[ "${BILLING_ENABLED}" != "True" && "${BILLING_ENABLED}" != "true" ]]; then
  echo "==> Setup partial complete (BigQuery + core APIs)."
  echo "Re-run after enabling billing to deploy Cloud Run."
  exit 0
fi

echo "==> Artifact Registry repo..."
gcloud artifacts repositories describe aegis --location="${REGION}" >/dev/null 2>&1 \
  || gcloud artifacts repositories create aegis \
       --repository-format=docker \
       --location="${REGION}" \
       --description="Aegis container images"

echo "==> Building and pushing image via Cloud Build..."
gcloud builds submit --tag "${IMAGE}:latest" .

echo "==> Deploying Cloud Run service ${SERVICE}..."
gcloud run deploy "${SERVICE}" \
  --image="${IMAGE}:latest" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="AEGIS_MODE=gcp,AEGIS_PROJECT_ID=${PROJECT},AEGIS_LOCATION=${REGION},AEGIS_MODEL=gemini-2.5-flash,AEGIS_JUDGE_MODEL=gemini-2.5-flash,AEGIS_BIGQUERY_DATASET=aegis_evals,AEGIS_BIGQUERY_TABLE=evaluation_runs"

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --format='value(status.url)')
echo "==> Deployed: ${URL}"
echo "Health: curl ${URL}/healthz"
