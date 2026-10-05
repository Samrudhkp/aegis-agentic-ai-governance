"""Application configuration for Aegis."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_THRESHOLDS = ROOT / "configs" / "thresholds.yaml"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AEGIS_",
        env_file=".env",
        extra="ignore",
    )

    project_id: str = Field(default="aegis-demo")
    location: str = Field(default="us-central1")
    model: str = Field(default="gemini-2.0-flash")
    judge_model: str = Field(default="gemini-2.0-flash")

    # Offline/local mode skips live Gemini/GCP calls and uses deterministic stubs.
    mode: Literal["local", "gcp"] = "local"

    bigquery_dataset: str = "aegis_evals"
    bigquery_table: str = "evaluation_runs"
    log_name: str = "aegis-eval"
    otel_service_name: str = "aegis-eval-api"

    thresholds_path: Path = DEFAULT_THRESHOLDS
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    cloud_run_service: str = "aegis-eval-api"
    fail_closed: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
