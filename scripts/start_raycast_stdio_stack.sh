#!/bin/sh
#
# Raycast passes MCP command arguments literally, so avoid bash -lc quoting
# entirely and delegate to the normal stdio stack launcher.

set -eu

export LC_ALL=C
export LANG=en_US.UTF-8
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export COPILOT_REUSE_EXISTING="${COPILOT_REUSE_EXISTING:-1}"
export COPILOT_PORT="${COPILOT_PORT:-4141}"
export CUSTOM_API_URL="${CUSTOM_API_URL:-http://localhost:4141/v1}"
export CUSTOM_API_KEY="${CUSTOM_API_KEY:-copilot-proxy}"
export CUSTOM_ALLOWED_MODELS="${CUSTOM_ALLOWED_MODELS:-copilot/claude-haiku-4.5,copilot/claude-opus-4.5,copilot/claude-sonnet-4.5,copilot/claude-sonnet-4.6,copilot/claude-sonnet-5,copilot/gemini-2.5-pro,copilot/gemini-3-flash-preview,copilot/gemini-3.1-pro-preview,copilot/gemini-3.5-flash,copilot/gemini-3.6-flash,copilot/gpt-4.1,copilot/gpt-4.1-2025-04-14,copilot/gpt-4o,copilot/gpt-5-mini,copilot/gpt-5.3-codex,copilot/gpt-5.4,copilot/gpt-5.4-mini,copilot/gpt-5.6-luna,copilot/gpt-5.6-terra,copilot/kimi-k2.7-code,copilot/mai-code-1-flash-picker,copilot/oswe-vscode-prime}"
export DEFAULT_MODEL="${DEFAULT_MODEL:-auto}"
export ZEN_MCP_FORCE_ENV_OVERRIDE="${ZEN_MCP_FORCE_ENV_OVERRIDE:-false}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

cd /Users/davidortiz/mcp-servers-official/zen-mcp-server
exec ./scripts/start_stdio_stack.sh "$@"
