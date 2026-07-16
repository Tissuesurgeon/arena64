# Arena64 full backend — API + AI competition runtime (+ skills/prompts)
# Build from monorepo root:
#   docker build -t arena64-backend .
# Railway: Root Directory = .  |  Dockerfile path = Dockerfile
# See docs/deploy.md

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

# API deps (includes httpx used by AI runtime)
COPY apps/api/requirements.txt /tmp/api-requirements.txt
COPY apps/ai-runtime/requirements.txt /tmp/runtime-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt \
    && pip install --no-cache-dir -r /tmp/runtime-requirements.txt \
    && rm -f /tmp/api-requirements.txt /tmp/runtime-requirements.txt

# FastAPI application
COPY apps/api/app ./app

# Competition runtime worker + agent skills / prompts
COPY apps/ai-runtime /runtime
COPY packages/agent-skills /agent-skills
COPY packages/prompts /agent-prompts

COPY scripts/start-backend.sh /start-backend.sh
RUN chmod +x /start-backend.sh

# PORT is injected by Railway (often 8080). start-backend.sh sets ARENA64_API_URL to match.
ENV RUNTIME_POLL_SECONDS=2.5 \
    RUNTIME_WORKER_ID=0

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health" >/dev/null || exit 1

CMD ["/start-backend.sh"]
