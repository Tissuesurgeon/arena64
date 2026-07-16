#!/bin/sh
# Start Arena64 API + AI competition runtime in one container (Railway / Docker).
set -eu

PORT="${PORT:-8000}"
# Same container: always hit the API on Railway's injected PORT (ignore stale :8000).
# Set ARENA64_API_EXTERNAL=1 to keep a custom ARENA64_API_URL (split-service deploys).
if [ -z "${ARENA64_API_EXTERNAL:-}" ]; then
  export ARENA64_API_URL="http://127.0.0.1:${PORT}"
fi

echo "Arena64 backend: API :${PORT} + AI runtime → ${ARENA64_API_URL}"

cd /app

uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" &
API_PID=$!

# Wait briefly for API to accept connections before starting the poller
i=0
while [ "$i" -lt 60 ]; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 1
done

python /runtime/main.py &
RUNTIME_PID=$!

shutdown() {
  echo "Shutting down backend (api=${API_PID} runtime=${RUNTIME_PID})"
  kill "${API_PID}" "${RUNTIME_PID}" 2>/dev/null || true
  wait "${API_PID}" "${RUNTIME_PID}" 2>/dev/null || true
}
trap shutdown INT TERM

while kill -0 "${API_PID}" 2>/dev/null && kill -0 "${RUNTIME_PID}" 2>/dev/null; do
  sleep 2
done

echo "A backend process exited — stopping the other"
shutdown
exit 1
