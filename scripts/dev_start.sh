#!/usr/bin/env bash
#
# Convenience launcher that starts the Copilot proxy, syncs the model registry,
# and then boots the Zen MCP server in a single command. Press Ctrl+C to stop
# everything.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COPILOT_PORT="${COPILOT_PORT:-4141}"
COPILOT_RATE_LIMIT="${COPILOT_RATE_LIMIT:-2}"

COPILOT_CMD=(
  npx
  copilot-api@latest
  start
  --port "${COPILOT_PORT}"
  --verbose
  --rate-limit "${COPILOT_RATE_LIMIT}"
  --wait
)

cleanup() {
  local exit_code=$?
  if [[ -n "${COPILOT_PID:-}" ]] && kill -0 "${COPILOT_PID}" 2>/dev/null; then
    echo "Stopping Copilot proxy (pid ${COPILOT_PID})..."
    kill "${COPILOT_PID}" 2>/dev/null || true
    wait "${COPILOT_PID}" 2>/dev/null || true
  fi
  exit "${exit_code}"
}

wait_for_proxy() {
  local tries=0
  local max_tries=60
  local url="http://localhost:${COPILOT_PORT}/v1/models"
  until curl -sSf "${url}" >/dev/null 2>&1; do
    tries=$((tries + 1))
    if (( tries >= max_tries )); then
      echo "Copilot API did not become ready on ${url} (timeout)" >&2
      return 1
    fi
    sleep 1
  done
}

echo "Starting Copilot proxy on port ${COPILOT_PORT}..."
"${COPILOT_CMD[@]}" &
COPILOT_PID=$!
trap cleanup EXIT INT TERM

if ! wait_for_proxy; then
  echo "Failed to confirm Copilot proxy readiness. Aborting." >&2
  exit 1
fi

echo "Synchronising Copilot models into conf/custom_models.json..."
python3 "${ROOT_DIR}/scripts/sync_copilot_models.py"

echo "Launching Zen MCP server..."
cd "${ROOT_DIR}"
./run-server.sh "$@"
