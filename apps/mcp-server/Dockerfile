# Arena64 MCP Server — optional Railway/sidecar service
# Build from this directory: docker build -f apps/mcp-server/Dockerfile apps/mcp-server
# Railway: Root Directory = apps/mcp-server
# Required env: ARENA64_API_URL, SERVICE_API_KEY

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# MCP stdio by default; HTTP mode if the server supports PORT later
CMD ["python", "server.py"]
