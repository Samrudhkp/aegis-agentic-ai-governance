# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AEGIS_MODE=local

WORKDIR /app

COPY pyproject.toml README.md ./
COPY aegis ./aegis
COPY configs ./configs

RUN pip install --upgrade pip && pip install .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')" || exit 1

CMD ["uvicorn", "aegis.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
