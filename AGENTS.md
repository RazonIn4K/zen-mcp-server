# Repository Guidelines

## Project Structure & Module Organization
Core orchestration lives in `server.py`, which exposes MCP entry points and coordinates multi-model workflows. Feature tools reside under `tools/`, model and provider adapters in `providers/`, and shared utilities in `utils/`. Prompts and system presets stay in `systemprompts/`. Configuration templates and automation scripts live in `conf/`, `scripts/`, and `docker/`. Unit tests are in `tests/`, while simulator-driven scenarios and log helpers sit in `simulator_tests/` (see `communication_simulator_test.py`). Long-form docs live in `docs/`; runtime logs rotate in `logs/`.

## Build, Test, and Development Commands
- `source .zen_venv/bin/activate` — load the managed Python toolchain.
- `./run-server.sh` — install dependencies, refresh `.env`, and launch the MCP server locally.
- `./code_quality_checks.sh` — run Ruff autofix, Black, isort, and the default pytest suite.
- `python communication_simulator_test.py --quick` — smoke-test multi-agent orchestration.
- `pytest -q` or `pytest tests/test_auto_mode_model_listing.py -q` — execute the full or targeted unit test suite.

## Coding Style & Naming Conventions
Target Python 3.9+ with Black and isort configured for 120-character lines. Ruff enforces pycodestyle, pyflakes, bugbear, comprehension, and pyupgrade rules; resolve fixes before committing. Prefer explicit type hints, snake_case modules, and descriptive function names. Extend workflows via inheritance or hooks rather than `hasattr` checks, and keep comments for non-obvious design choices.

## Testing Guidelines
Pytest is the primary framework. Mirror production modules under `tests/` and name tests `test_<behavior>` or `Test<Feature>`. Run `python -m pytest tests/ -v -m "not integration"` before every commit; add `--cov=. --cov-report=html` for coverage-sensitive changes. Use `python communication_simulator_test.py --verbose` or `--individual <case>` to validate cross-provider flows. Capture relevant excerpts from `logs/mcp_server.log` or `logs/mcp_activity.log` when failures occur.

## Commit & Pull Request Guidelines
Use Conventional Commits (`feat(scope): summary`, etc.) and keep each change focused. Reference issues or simulator cases when useful. Pull requests should explain intent, list validation commands executed, and flag configuration or tool toggles. Attach logs or screenshots if behavior changes. Ensure the branch is rebased and CI-ready before requesting review.

## Security & Configuration Tips
Never commit secrets or generated log artifacts. Store provider URLs and API keys in `.env` or your MCP client config. Run `./run-server.sh` after dependency or environment updates to regenerate `.env` and verify connectivity. When adding providers or tools, sanitize prompts, document new environment variables in `docs/`, and update `claude_config_example.json` if default capabilities change.
