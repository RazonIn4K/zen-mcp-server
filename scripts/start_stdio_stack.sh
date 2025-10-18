#!/usr/bin/env bash
#
# Bootstraps the Copilot API proxy and the Zen MCP server in stdio mode
# without printing any non-JSON output. Designed for MCP clients that expect
# a clean stdio channel (Claude Desktop, Claude Code CLI, Gemini CLI, Zed, etc).
#
# All operational logs are written to the repo's logs/ directory:
#   - stack_stdio.log           high-level lifecycle events
#   - copilot-proxy.log         proxy stdout/stderr
#   - sync_copilot_models.log   model sync results
#   - run-server.log            env bootstrap output
#
# Environment variables you can override:
#   COPILOT_PORT           (default: 4141)
#   COPILOT_RATE_LIMIT     (default: 2)
#   COPILOT_DIR_OVERRIDE   (path to a copilot-api checkout)
#   CUSTOM_API_URL / KEY   forwarded to the server via .env or MCP config
#   ZEN_STDIO_SILENT       set to 0 to surface setup logs on stderr

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "${LOG_DIR}"

STACK_LOG="${LOG_DIR}/stack_stdio.log"
PROXY_LOG="${LOG_DIR}/copilot-proxy.log"
SYNC_LOG="${LOG_DIR}/sync_copilot_models.log"
RUNSERVER_LOG="${LOG_DIR}/run-server.log"

COPILOT_PORT="${COPILOT_PORT:-4141}"
COPILOT_RATE_LIMIT="${COPILOT_RATE_LIMIT:-2}"
LOCAL_COPILOT_DIR_DEFAULT="$(cd "${ROOT_DIR}/.." && pwd)/copilot-api"
COPILOT_DIR="${COPILOT_DIR_OVERRIDE:-$LOCAL_COPILOT_DIR_DEFAULT}"
COPILOT_ARGS=(--port "${COPILOT_PORT}" --verbose)
if [[ -n "${COPILOT_RATE_LIMIT}" ]]; then
  COPILOT_ARGS+=(--rate-limit "${COPILOT_RATE_LIMIT}" --wait)
fi

timestamp() {
  date +"%Y-%m-%dT%H:%M:%S%z"
}

log() {
  local message="$*"
  if [[ "${ZEN_STDIO_SILENT:-1}" == "0" ]]; then
    printf '%s %s\n' "$(timestamp)" "${message}" >&2
  fi
  printf '%s %s\n' "$(timestamp)" "${message}" >>"${STACK_LOG}"
}

cleanup() {
  local exit_code=$?
  if [[ -n "${COPILOT_PID:-}" ]] && kill -0 "${COPILOT_PID}" 2>/dev/null; then
    log "Stopping Copilot proxy (pid ${COPILOT_PID})"
    kill "${COPILOT_PID}" 2>/dev/null || true
    wait "${COPILOT_PID}" 2>/dev/null || true
  fi
  exit "${exit_code}"
}
trap cleanup EXIT INT TERM

wait_for_proxy() {
  local tries=0
  local max_tries=60
  local url="http://localhost:${COPILOT_PORT}/v1/models"

  while ! curl -sSf "${url}" >/dev/null 2>&1; do
    tries=$((tries + 1))
    if (( tries >= max_tries )); then
      return 1
    fi
    sleep 1
  done
}

start_copilot_proxy() {
  if [[ -d "${COPILOT_DIR}" && -f "${COPILOT_DIR}/package.json" && -f "${COPILOT_DIR}/bun.lock" ]] && command -v bun >/dev/null 2>&1; then
    log "Starting Copilot proxy from local checkout: ${COPILOT_DIR}"
    (
      cd "${COPILOT_DIR}"
      if [[ ! -d node_modules ]]; then
        log "Installing copilot-api dependencies with bun..."
        bun install --silent >>"${PROXY_LOG}" 2>&1
      fi
      bun run start -- start "${COPILOT_ARGS[@]}" >>"${PROXY_LOG}" 2>&1
    ) &
  else
    log "Starting Copilot proxy via npm package on port ${COPILOT_PORT}"
    (
      npx copilot-api@latest start "${COPILOT_ARGS[@]}" >>"${PROXY_LOG}" 2>&1
    ) &
  fi
  COPILOT_PID=$!
}

# ---------------------------------------------------------------------------
# Bootstrap sequence
# ---------------------------------------------------------------------------

log "Bootstrap starting (stdio-safe stack)"
log "Logs: ${STACK_LOG}"
log "Proxy log: ${PROXY_LOG}"
log "Sync log: ${SYNC_LOG}"
log "Run-server log: ${RUNSERVER_LOG}"

start_copilot_proxy
if ! wait_for_proxy; then
  log "Copilot API failed to become ready on port ${COPILOT_PORT}"
  exit 1
fi
log "Copilot API online at http://localhost:${COPILOT_PORT}"

log "Synchronising Copilot models into conf/custom_models.json..."
python3 "${ROOT_DIR}/scripts/sync_copilot_models.py" >>"${SYNC_LOG}" 2>&1

export ZEN_SKIP_INTEGRATIONS=1
export ZEN_STDIO_SILENT="${ZEN_STDIO_SILENT:-1}"

log "Preparing Zen environment via run-server.sh"
( cd "${ROOT_DIR}" && ./run-server.sh "$@" ) >>"${RUNSERVER_LOG}" 2>&1

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/.env"
  set +a
fi

PYTHON_BIN="${ROOT_DIR}/.zen_venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  log "Python virtualenv not found at ${PYTHON_BIN}"
  exit 1
fi

log "Handing off to server.py (stdio mode)"
"${PYTHON_BIN}" "${ROOT_DIR}/server.py" "$@"
