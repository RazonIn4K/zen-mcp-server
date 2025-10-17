# MCP Client Configuration Cheatsheet

Use the stdio-safe launcher (`scripts/start_stdio_stack.sh`) whenever an MCP client needs to spawn Zen and the GitHub Copilot proxy together. The launcher hides all setup noise, updates `conf/custom_models.json`, keeps the proxy in sync, and exits cleanly so the client receives only JSON-RPC messages.

> **Why `bash -lc`?**  
> `-l` starts a login shell so your `~/.bash_profile` / `~/.bashrc` PATH edits take effect, and `-c` executes the command string. This ensures tools installed with Homebrew, asdf, pyenv, etc. are available when the MCP client spawns Zen.

All snippets below assume you cloned Zen into `~/mcp-servers-official/zen-mcp-server`. Adjust paths to match your setup.

## Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "zen": {
      "command": "bash",
      "args": [
        "-lc",
        "cd ~/mcp-servers-official/zen-mcp-server && ./scripts/start_stdio_stack.sh"
      ],
      "env": {
        "CUSTOM_API_URL": "http://localhost:4141/v1",
        "CUSTOM_API_KEY": "copilot-proxy",
        "CUSTOM_ALLOWED_MODELS": "copilot/claude-sonnet-4.5,copilot/claude-haiku-4.5,copilot/gpt-5,copilot/gpt-5-codex,copilot/gpt-5-mini,copilot/o4-mini,copilot/gemini-2-5-pro,copilot/grok-code-fast-1",
        "DEFAULT_MODEL": "auto",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Claude Code CLI (`~/.config/claude-code/mcp.json`)

```json
{
  "mcpServers": {
    "zen": {
      "command": "bash",
      "args": [
        "-lc",
        "cd ~/mcp-servers-official/zen-mcp-server && ./scripts/start_stdio_stack.sh"
      ],
      "env": {
        "CUSTOM_API_URL": "http://localhost:4141/v1",
        "CUSTOM_API_KEY": "copilot-proxy",
        "CUSTOM_ALLOWED_MODELS": "copilot/claude-sonnet-4.5,copilot/claude-haiku-4.5,copilot/gpt-5,copilot/gpt-5-codex,copilot/gpt-5-mini,copilot/o4-mini,copilot/gemini-2-5-pro,copilot/grok-code-fast-1",
        "DEFAULT_MODEL": "auto",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Gemini CLI (`~/.gemini/settings.json`)

```json
{
  "mcpServers": {
    "zen": {
      "command": "bash",
      "args": [
        "-lc",
        "cd ~/mcp-servers-official/zen-mcp-server && ./scripts/start_stdio_stack.sh"
      ],
      "env": {
        "CUSTOM_API_URL": "http://localhost:4141/v1",
        "CUSTOM_API_KEY": "copilot-proxy",
        "CUSTOM_ALLOWED_MODELS": "copilot/claude-sonnet-4.5,copilot/claude-haiku-4.5,copilot/gpt-5,copilot/gpt-5-codex,copilot/gpt-5-mini,copilot/o4-mini,copilot/gemini-2-5-pro,copilot/grok-code-fast-1",
        "DEFAULT_MODEL": "auto",
        "LOG_LEVEL": "INFO"
      },
      "timeout": 60000
    }
  }
}
```

## Zed (`~/.config/zed/settings.json`)

```json
{
  "context_servers": {
    "zen": {
      "source": "custom",
      "enabled": true,
      "command": "bash",
      "args": [
        "-lc",
        "cd ~/mcp-servers-official/zen-mcp-server && ./scripts/start_stdio_stack.sh"
      ],
      "env": {
        "CUSTOM_ALLOWED_MODELS": "copilot/claude-sonnet-4.5,copilot/claude-haiku-4.5,copilot/gpt-5,copilot/gpt-5-codex,copilot/gpt-5-mini,copilot/o4-mini,copilot/gemini-2-5-pro,copilot/grok-code-fast-1",
        "DEFAULT_MODEL": "auto",
        "CUSTOM_API_URL": "http://localhost:4141/v1",
        "CUSTOM_API_KEY": "copilot-proxy",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Model Selection Tips

- The `CUSTOM_ALLOWED_MODELS` list guarantees only the newest GitHub Copilot models appear inside Zen. Adjust it after running `scripts/sync_copilot_models.py --dry-run` to inspect fresh aliases.
- `DEFAULT_MODEL=auto` delegates to Zen’s auto-selector, which already prioritises the latest 4.5 Claude models, GPT-5 tiers, o4-mini, Gemini 2.5 Pro, and Grok code models when available.
- To double-check availability, run `use zen listmodels` (Claude Code) or `gemini mcp run zen listmodels`.

## Quick Validation

```bash
# One-off sanity check from the repo (requires `timeout` from coreutils)
cd ~/mcp-servers-official/zen-mcp-server
timeout 15s ./scripts/start_stdio_stack.sh >/tmp/zen_stdio.out 2>/tmp/zen_stdio.err || true
head -n 5 /tmp/zen_stdio.out   # should be empty until a client connects
tail -n 5 logs/stack_stdio.log
```

When integrating with a new client, restart the client after editing its configuration and run `listmodels` to verify the Copilot catalogue synchronised correctly.
