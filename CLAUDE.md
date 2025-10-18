# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zen MCP Server is a Model Context Protocol (MCP) server that enables AI orchestration across multiple AI providers (Gemini, OpenAI, Azure, XAI, OpenRouter, Ollama, etc.). It provides specialized tools for code analysis, debugging, planning, and collaborative AI-to-AI conversations with conversation continuity.

**Key Differentiator**: Multi-turn conversation memory that persists across stateless MCP protocol requests, enabling true AI-to-AI collaboration where different tools can seamlessly continue conversations started by other tools.

## Architecture Overview

### Core Components

**server.py** - MCP protocol boundary and orchestration hub
- Handles MCP tool discovery, registration, and execution
- Implements conversation thread reconstruction for stateful continuity
- Performs early model resolution and validation at MCP boundary
- Routes tool calls to appropriate handlers with pre-resolved model context
- Key functions: `handle_call_tool()`, `reconstruct_thread_context()`, `configure_providers()`

**utils/conversation_memory.py** - Stateful conversation system for stateless protocol
- In-memory conversation persistence with UUID-based thread identification
- Dual prioritization strategy: newest-first file prioritization, newest-first turn collection with chronological presentation
- Cross-tool continuation support (e.g., analyze → codereview → debug with full context)
- Token-aware history building with intelligent file/turn exclusion
- Key functions: `create_thread()`, `add_turn()`, `build_conversation_history()`, `get_conversation_file_list()`

**providers/** - AI model provider abstractions
- `base.py`: Abstract `ModelProvider` interface defining provider contract
- `registry.py`: Central `ModelProviderRegistry` for provider management and model resolution
- `shared/`: Common types (`ModelCapabilities`, `ModelResponse`, `ProviderType`)
- `registries/`: Model catalogs for each provider (Gemini, OpenAI, Azure, XAI, OpenRouter, Custom)
- Provider initialization order: Native APIs → Custom endpoints → OpenRouter (catch-all)

**tools/** - Specialized AI-powered tool implementations
- `simple/base.py`: Base class for simple single-call tools (`SimpleTool`)
- `workflow/base.py`: Base class for multi-step workflow tools (`WorkflowTool`)
- Each tool defines: name, description, input schema, model requirements, execution logic
- Tools can be disabled via `DISABLED_TOOLS` environment variable
- Key tools: chat, clink (CLI bridge), thinkdeep, planner, consensus, codereview, precommit, debug

**systemprompts/** - System prompts for each tool
- Centralized prompt definitions separate from tool logic
- CS-Brain base class pattern for structured reasoning workflows
- Each tool has a corresponding `<tool>_prompt.py` module

**utils/** - Shared utilities and services
- `file_utils.py`: File reading with token estimation and line number formatting
- `model_context.py`: Model-specific token allocation and capability management
- `model_restrictions.py`: Provider-specific model allowlist enforcement
- `client_info.py`: MCP client detection and friendly name mapping
- `token_utils.py`: Token estimation and budget validation

### Critical Architectural Patterns

**Conversation Continuity Across Stateless Protocol**
The MCP protocol is stateless (each request is independent), but Zen bridges this gap:
1. Tools create conversation threads with `create_thread()` returning UUID
2. Each turn stored with `add_turn()` including files, tool attribution, model metadata
3. Subsequent requests include `continuation_id` parameter
4. `server.py:reconstruct_thread_context()` loads full history from memory
5. `build_conversation_history()` embeds conversation + files into tool prompt
6. Any tool can continue conversations started by other tools

**Dual File Prioritization Strategy**
When same file appears in multiple conversation turns:
- Collection: Walk backwards through turns (newest → oldest)
- Priority: First occurrence (newest) wins, older duplicates excluded
- Token limits: Older files excluded first when budget constrained
- Applies across entire conversation chain, not just current thread

**Early Model Resolution at MCP Boundary**
`server.py:handle_call_tool()` resolves models before tool execution:
1. Parse `model:option` format (handles OpenRouter suffixes, Ollama tags, consensus stances)
2. Auto mode → specific model via `get_preferred_fallback_model()`
3. Validate model availability against restrictions
4. Create `ModelContext` with capabilities and token allocation
5. Pass `_model_context` to tool for consistent behavior

**Provider Registry Pattern**
`ModelProviderRegistry` uses lazy initialization singleton pattern:
- Providers registered at startup via `configure_providers()`
- Provider instances created on first use (not at registration)
- Model resolution cascades through providers in priority order
- Restriction service filters available models per provider

## Development Commands

### Environment Setup
```bash
# Setup server (handles venv, dependencies, .env, MCP config)
./run-server.sh

# View server logs in real-time
./run-server.sh -f
tail -f logs/mcp_server.log
```

### Code Quality & Testing
```bash
# Activate virtual environment (REQUIRED before any command)
source .zen_venv/bin/activate

# Run ALL quality checks (linting + formatting + tests) - USE THIS BEFORE COMMITS
./code_quality_checks.sh

# Run unit tests only (excludes integration tests requiring API keys)
python -m pytest tests/ -v -m "not integration"

# Run specific test file
python -m pytest tests/test_conversation_memory.py -v

# Run specific test function
python -m pytest tests/test_conversation_memory.py::TestConversationMemory::test_create_thread -v

# Run integration tests (requires Ollama running locally - FREE unlimited)
./run_integration_tests.sh

# Run integration tests + simulator tests
./run_integration_tests.sh --with-simulator
```

### Simulator Testing (End-to-End Validation)
```bash
# Quick test mode - 6 essential tests covering core functionality
python communication_simulator_test.py --quick

# Run all simulator tests
python communication_simulator_test.py

# List available tests
python communication_simulator_test.py --list-tests

# Run individual test for isolation and debugging (RECOMMENDED)
python communication_simulator_test.py --individual cross_tool_continuation
python communication_simulator_test.py --individual conversation_chain_validation

# Run with verbose output
python communication_simulator_test.py --individual memory_validation --verbose
```

**IMPORTANT**: After code changes, restart Claude session for changes to take effect in MCP server.

### Linting & Formatting
```bash
# Auto-fix issues
ruff check . --fix
black .
isort .

# Check without fixing
ruff check .
black --check .
isort --check-only .
```

## Key Files to Understand

**Conversation Memory System**
- `utils/conversation_memory.py` - Thread management, history building, file prioritization (lines 1-120 for architecture, 433-636 for file prioritization, 638-1027 for history building)
- `server.py` - Thread reconstruction at MCP boundary (lines 967-1286 for `reconstruct_thread_context()`)

**Provider System**
- `providers/base.py` - Abstract provider interface (lines 1-50 for interface definition)
- `providers/registry.py` - Provider registry and model resolution
- `server.py` - Provider configuration (lines 379-628 for `configure_providers()`)

**Tool System**
- `tools/simple/base.py` - Simple tool base class
- `tools/workflow/base.py` - Workflow tool base class
- `tools/chat.py` - Example simple tool with conversation support
- `server.py` - Tool registration and filtering (lines 260-282 for tool registry)

**Model Context & Token Management**
- `utils/model_context.py` - Model capabilities and token allocation
- `utils/file_utils.py` - File reading with token estimation
- `utils/token_utils.py` - Token estimation utilities

## Configuration & Environment

### Essential Environment Variables
```bash
# API Keys (at least one required)
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
XAI_API_KEY=your_key_here
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_here

# Custom/Local Models (Ollama, vLLM, etc.)
CUSTOM_API_URL=http://localhost:11434
CUSTOM_API_KEY=  # Optional, empty for Ollama
CUSTOM_MODEL_NAME=llama3.2

# Model Configuration
DEFAULT_MODEL=auto  # or specific model name
DEFAULT_THINKING_MODE_THINKDEEP=medium  # low, medium, high, max

# Tool Configuration (disable unused tools to save context)
DISABLED_TOOLS=analyze,refactor,testgen,secaudit,docgen,tracer

# Conversation Limits
MAX_CONVERSATION_TURNS=50  # Maximum turns per conversation thread
CONVERSATION_TIMEOUT_HOURS=3  # Thread expiration time

# Model Restrictions (optional allowlists)
GOOGLE_ALLOWED_MODELS=gemini-2.5-flash,gemini-2.5-pro
OPENAI_ALLOWED_MODELS=o3-mini,gpt-5-pro

# Logging
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
ZEN_STDIO_SILENT=0  # Set to 1 to mute stderr logging for MCP stdio mode

# Environment Override (for Claude Code/Desktop conflicts)
ZEN_MCP_FORCE_ENV_OVERRIDE=1  # .env overrides system environment
```

### Tool Disabling Strategy
Only enable tools you need - each tool consumes context window space:
- **Always enabled**: version, listmodels (cannot be disabled)
- **Enabled by default**: chat, clink, thinkdeep, planner, consensus, codereview, precommit, debug, apilookup, challenge
- **Disabled by default**: analyze, refactor, testgen, secaudit, docgen, tracer

## Common Development Workflows

### Adding a New Tool
1. Create `tools/your_tool.py` extending `SimpleTool` or `WorkflowTool`
2. Create `systemprompts/your_tool_prompt.py` with system prompt
3. Add to `TOOLS` dictionary in `server.py`
4. Add to `PROMPT_TEMPLATES` in `server.py` for CLI shortcuts
5. Add unit tests in `tests/test_your_tool.py`
6. Add simulator test in `simulator_tests/test_your_tool.py`
7. Update documentation in `docs/tools/your_tool.md`

### Adding a New Provider
1. Create `providers/your_provider.py` extending `ModelProvider`
2. Create `providers/registries/your_provider.py` with model catalog
3. Add provider registration in `server.py:configure_providers()`
4. Add API key environment variable
5. Add unit tests in `tests/test_your_provider.py`
6. Update `docs/adding_providers.md` with setup instructions

### Debugging Conversation Continuity Issues
1. Check logs: `tail -f logs/mcp_server.log | grep CONVERSATION_DEBUG`
2. Verify thread creation: Look for `[THREAD] Created new thread <uuid>`
3. Check thread retrieval: Look for `[CONVERSATION_DEBUG] Looking up thread <uuid>`
4. Validate file prioritization: Look for `[FILES]` log entries showing newest-first ordering
5. Monitor token allocation: Look for `[CONVERSATION_DEBUG] Token budget calculation`
6. Use simulator tests: `python communication_simulator_test.py --individual cross_tool_continuation --verbose`

### Before Making Changes
1. Activate venv: `source .zen_venv/bin/activate`
2. Run quality checks: `./code_quality_checks.sh`
3. Check server logs: `tail -n 50 logs/mcp_server.log`

### After Making Changes
1. Run quality checks: `./code_quality_checks.sh`
2. Run integration tests: `./run_integration_tests.sh`
3. Run quick simulator tests: `python communication_simulator_test.py --quick`
4. Check logs for errors: `tail -n 100 logs/mcp_server.log`
5. **Restart Claude session** to load updated MCP server code

### Before Committing/PR
1. Final quality check: `./code_quality_checks.sh` (must pass 100%)
2. Run integration tests: `./run_integration_tests.sh`
3. Run quick tests: `python communication_simulator_test.py --quick`
4. Optional full suite: `./run_integration_tests.sh --with-simulator`
5. Follow commit format: `feat:`, `fix:`, `docs:`, `chore:`, etc.

## Testing Strategy

**Unit Tests** (`tests/`) - Fast, no API keys required
- Mock providers, isolated component testing
- Run before every commit: `python -m pytest tests/ -v -m "not integration"`

**Integration Tests** (`tests/` with `@pytest.mark.integration`) - Local models via Ollama
- Real API calls to local Ollama models (FREE unlimited)
- Requires Ollama running: `ollama serve` + `ollama pull llama3.2`
- Run with: `./run_integration_tests.sh` or `python -m pytest tests/ -v -m "integration"`

**Simulator Tests** (`simulator_tests/`) - End-to-end validation
- Tests full MCP server communication flow
- Uses configured API keys (Gemini/OpenAI/etc.)
- Run individually for best isolation: `python communication_simulator_test.py --individual <test_name>`
- Quick mode for time-limited testing: `python communication_simulator_test.py --quick`

## Troubleshooting

### Common Issues

**Linting Failures**
```bash
ruff check . --fix
black .
isort .
```

**Test Failures**
```bash
# Quick diagnosis
python communication_simulator_test.py --quick --verbose

# Detailed investigation
python communication_simulator_test.py --individual <test_name> --verbose
tail -f logs/mcp_server.log
```

**Server Not Starting**
```bash
./run-server.sh  # Re-run setup
grep "ERROR" logs/mcp_server.log | tail -20
which python  # Should show .zen_venv/bin/python
```

**Conversation Context Lost**
- Check thread ID format (must be valid UUID)
- Verify thread hasn't expired (default 3 hours)
- Check logs for thread lookup: `grep "thread:<uuid>" logs/mcp_server.log`
- Ensure MCP server process is persistent (not restarting between requests)

## Documentation References

- **Setup**: `docs/getting-started.md` - Complete installation guide
- **Tools**: `docs/tools/` - Individual tool documentation
- **Providers**: `docs/adding_providers.md` - Provider setup and configuration
- **Advanced**: `docs/advanced-usage.md` - Complex workflows and power features
- **Configuration**: `docs/configuration.md` - Environment variables and restrictions
- **Troubleshooting**: `docs/troubleshooting.md` - Common issues and solutions
- **Contributing**: `docs/contributions.md` - Code standards and PR process
- **Prompt Examples**: `docs/zen_prompt_playbook.md` - Tool usage templates

## Code Standards

- Python 3.9+ with type hints
- Black formatting (120 char line limit)
- isort for import organization (stdlib → third-party → local)
- Ruff linting (pycodestyle, pyflakes, bugbear, comprehension, pyupgrade)
- Docstrings for all public functions and classes
- Inheritance-based contracts over dynamic attribute checking
- Prefer explicit over implicit behavior

## Important Notes

1. **Virtual Environment**: Always activate `.zen_venv` before running commands
2. **Session Restart**: Changes to Python code require Claude session restart
3. **Log Files**: `logs/mcp_server.log` (all activity), `logs/mcp_activity.log` (tool calls only)
4. **Token Management**: File size checks at MCP boundary, conversation history token allocation
5. **Test Isolation**: Run simulator tests individually for better debugging
6. **Commit Format**: Use conventional commit prefixes (feat/fix/docs/chore/test/ci)
