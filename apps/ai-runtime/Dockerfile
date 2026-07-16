# Arena64 AI Runtime — production image for Railway
# Build from monorepo root (skills + prompts live under packages/):
#   docker build -f apps/ai-runtime/Dockerfile .
# Railway: Root Directory = repo root, Dockerfile path = apps/ai-runtime/Dockerfile

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY apps/ai-runtime/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/ai-runtime/ .
COPY packages/agent-skills /agent-skills
COPY packages/prompts /agent-prompts

# Runtime polls the API; no HTTP port required
CMD ["python", "main.py"]
