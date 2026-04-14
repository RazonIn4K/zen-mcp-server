#!/usr/bin/env bash
#
# Convenience launcher that starts the Copilot proxy, syncs the model registry,
# and then boots the Zen MCP server in a single command. Press Ctrl+C to stop
# everything.
#
# NOTE: This script is verbose and prints setup progress to the terminal.
#       MCP clients that require a pristine stdio channel (Claude Desktop,
#       Claude Code CLI, Gemini CLI, Zed, etc.) should call
#       scripts/start_stdio_stack.sh instead.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COPILOT_PORT="${COPILOT_PORT:-4141}"
COPILOT_RATE_LIMIT="${COPILOT_RATE_LIMIT:-2}"
COPILOT_REUSE_EXISTING="${COPILOT_REUSE_EXISTING:-0}"
COPILOT_PID=""
COPILOT_MANAGED=1
LOCAL_COPILOT_DIR_DEFAULT="$(cd "${ROOT_DIR}/.." && pwd)/copilot-api"
COPILOT_DIR="${COPILOT_DIR_OVERRIDE:-$LOCAL_COPILOT_DIR_DEFAULT}"
COPILOT_ARGS=(--port "${COPILOT_PORT}" --verbose)
if [[ -n "${COPILOT_RATE_LIMIT}" ]]; then
  COPILOT_ARGS+=(--rate-limit "${COPILOT_RATE_LIMIT}" --wait)
fi

log() {
  printf '%s\n' "$*" >&2
}

cleanup() {
  local exit_code=$?
  if (( COPILOT_MANAGED == 1 )) && [[ -n "${COPILOT_PID}" ]] && kill -0 "${COPILOT_PID}" 2>/dev/null; then
    log "Stopping Copilot proxy (pid ${COPILOT_PID})..."
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
      log "Copilot API did not become ready on ${url} (timeout)"
      return 1
    fi
    sleep 1
  done
}

is_port_listening() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -PiTCP:"${COPILOT_PORT}" -sTCP:LISTEN -t >/dev/null 2>&1
  elif command -v nc >/dev/null 2>&1; then
    nc -z localhost "${COPILOT_PORT}" >/dev/null 2>&1
  else
    netstat -an 2>/dev/null | grep -E "[.:]${COPILOT_PORT}[^0-9].*LISTEN" >/dev/null 2>&1
  fi
}

if is_port_listening; then
  if [[ "${COPILOT_REUSE_EXISTING}" == "1" ]]; then
    COPILOT_MANAGED=0
    log "Reusing existing Copilot proxy on port ${COPILOT_PORT}"
  else
    log "Port ${COPILOT_PORT} already in use. Set COPILOT_REUSE_EXISTING=1 to reuse it or choose another port."
    exit 1
  fi
fi

if (( COPILOT_MANAGED == 1 )) && [[ -d "${COPILOT_DIR}" && -f "${COPILOT_DIR}/package.json" && -f "${COPILOT_DIR}/bun.lock" ]] && command -v bun >/dev/null 2>&1; then
  log "Starting Copilot proxy from local checkout: ${COPILOT_DIR}"
  (
    cd "${COPILOT_DIR}"
    if [[ ! -d node_modules ]]; then
      log "Installing copilot-api dependencies with bun..."
      bun install --silent >&2
    fi
    bun run start -- start "${COPILOT_ARGS[@]}"
  ) &
  COPILOT_PID=$!
elif (( COPILOT_MANAGED == 1 )); then
  log "Starting Copilot proxy via npm package on port ${COPILOT_PORT}..."
  COPILOT_CMD=(
    npx
    copilot-api@latest
    start
    "${COPILOT_ARGS[@]}"
  )
  "${COPILOT_CMD[@]}" &
  COPILOT_PID=$!
fi
trap cleanup EXIT INT TERM

if ! wait_for_proxy; then
  log "Failed to confirm Copilot proxy readiness. Aborting."
  exit 1
fi

log "Synchronising Copilot models into conf/custom_models.json..."
python3 "${ROOT_DIR}/scripts/sync_copilot_models.py" >&2

export ZEN_SKIP_INTEGRATIONS=1

log "Preparing Zen environment..."
( cd "${ROOT_DIR}" && ./run-server.sh "$@" ) >&2

# Ensure environment variables from .env are available to the Python process
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi

cd "${ROOT_DIR}"
PYTHON_BIN="${ROOT_DIR}/.zen_venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  log "Python virtualenv not found at $PYTHON_BIN"
  exit 1
fi

log "Starting Zen MCP server (stdio)..."
"$PYTHON_BIN" server.py "$@" &
SERVER_PID=$!
wait "$SERVER_PID"
STATUS=$?
exit "$STATUS"
