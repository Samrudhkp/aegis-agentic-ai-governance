-- BigQuery schema for Aegis evaluation observability
CREATE SCHEMA IF NOT EXISTS aegis_evals;

CREATE TABLE IF NOT EXISTS aegis_evals.evaluation_runs (
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

-- Example dashboard query: quality over time
-- SELECT
--   TIMESTAMP_TRUNC(created_at, HOUR) AS hour,
--   AVG(overall) AS avg_overall,
--   AVG(safety) AS avg_safety,
--   AVG(risk_score) AS avg_risk,
--   COUNTIF(deploy_allowed) / COUNT(*) AS deploy_pass_rate
-- FROM aegis_evals.evaluation_runs
-- GROUP BY 1
-- ORDER BY 1 DESC;
