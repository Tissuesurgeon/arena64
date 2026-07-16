#!/bin/sh
# Start Arena64 API + AI competition runtime in one container (Railway / Docker).
set -eu

PORT="${PORT:-8000}"
# Runtime talks to the API in this same container unless overridden
export ARENA64_API_URL="${ARENA64_API_URL:-http://127.0.0.1:${PORT}}"

echo "Arena64 backend: API :${PORT} + AI runtime → ${ARENA64_API_URL}"

cd /app
python /runtime/main.py &
RUNTIME_PID=$!

uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" &
API_PID=$!

shutdown() {
  echo "Shutting down backend (api=${API_PID} runtime=${RUNTIME_PID})"
  kill "${API_PID}" "${RUNTIME_PID}" 2>/dev/null || true
  wait "${API_PID}" "${RUNTIME_PID}" 2>/dev/null || true
}
trap shutdown INT TERM

# Exit if either process dies
while kill -0 "${API_PID}" 2>/dev/null && kill -0 "${RUNTIME_PID}" 2>/dev/null; do
  sleep 2
done

echo "A backend process exited — stopping the other"
shutdown
exit 1
