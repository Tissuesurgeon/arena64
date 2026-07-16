# Arena64 API — production image for Railway
# Build from monorepo root (required — COPY paths are relative to context):
#   docker build -f apps/api/Dockerfile .
# Railway: Root Directory = . (repo root)
#          Dockerfile path = apps/api/Dockerfile
#          Config file (optional) = apps/api/railway.toml

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app

# Railway injects PORT; default 8000 for local docker runs
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health" >/dev/null || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
