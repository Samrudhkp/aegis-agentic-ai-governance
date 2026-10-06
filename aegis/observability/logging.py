"""Structured logging via stdlib / Cloud Logging."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from aegis.config import Settings, get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "aegis"):
            payload["aegis"] = getattr(record, "aegis")
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings | None = None) -> logging.Logger:
    settings = settings or get_settings()
    logger = logging.getLogger("aegis")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    if settings.mode == "gcp":
        try:
            import google.cloud.logging as cloud_logging

            client = cloud_logging.Client(project=settings.project_id)
            client.setup_logging(log_level=logging.INFO)
            logger.info(
                "Cloud Logging configured",
                extra={"aegis": {"log_name": settings.log_name}},
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Cloud Logging unavailable: %s", exc)

    return logger


def log_evaluation(run_payload: dict[str, Any]) -> None:
    logger = logging.getLogger("aegis")
    logger.info(
        "evaluation_completed",
        extra={"aegis": run_payload},
    )
