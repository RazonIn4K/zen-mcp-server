#!/usr/bin/env python3
"""
Sync GitHub Copilot models into Zen's custom model registry.

The script queries an OpenAI-compatible proxy (for example, `copilot-api`)
for the `/models` listing, creates `copilot/<alias>` entries for each model,
and writes them into ``conf/custom_models.json`` so the Custom provider can
route requests through Zen.

Usage synopsis:

    python3 scripts/sync_copilot_models.py
    python3 scripts/sync_copilot_models.py --dry-run
    python3 scripts/sync_copilot_models.py --base-url http://host:port/v1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

DEFAULT_BASE_URL = "http://localhost:4141/v1"
DEFAULT_ALIAS_PREFIX = "copilot"
DEFAULT_TIMEOUT = 15
OUTDATED_COPILOT_MODEL_PREFIXES = (
    "gpt-3.5",
    "gpt-4",
    "gpt-4o",
    "gpt-4-o",
    "gpt-4.1",
    "gpt-41",
    "gpt-5.1",
    "gpt-5.2",
    "gpt-5-mini",
    "text-embedding-",
)
OUTDATED_COPILOT_MODEL_IDS = {
    "claude-opus-4.5",
    "claude-sonnet-4",
    "claude-sonnet-4.5",
    "gemini-2.5-pro",
}

ALIAS_SANITISE_PATTERN = re.compile(r"[^a-z0-9]+")
SEMANTIC_COPILOT_ALIASES = {
    "claude-opus-4.6": ["opus", "claude"],
    "claude-sonnet-4.6": ["sonnet"],
    "claude-haiku-4.5": ["haiku"],
    "gemini-3.1-pro-preview": ["gemini"],
    "gemini-3-flash-preview": ["gemini-flash"],
    "gpt-5.4": ["gpt"],
    "gpt-5.4-mini": ["gpt-mini"],
    "gpt-5.3-codex": ["codex"],
    "grok-code-fast-1": ["grok-code"],
    "minimax-m2.5": ["minimax"],
    "oswe-vscode-prime": ["raptor-prime", "raptor-mini"],
    "oswe-vscode-secondary": ["raptor-secondary"],
}

DEFAULT_README = {
    "description": "Model metadata for local/self-hosted OpenAI-compatible endpoints (Custom provider).",
    "documentation": "https://github.com/BeehiveInnovations/zen-mcp-server/blob/main/docs/custom_models.md",
    "usage": "Each entry will be advertised by the Custom provider. Aliases are case-insensitive.",
    "field_notes": "Matches providers/shared/model_capabilities.py.",
    "field_descriptions": {
        "model_name": "The model identifier e.g., 'llama3.2'",
        "aliases": "Array of short names users can type instead of the full model name",
        "context_window": "Total number of tokens the model can process (input + output combined)",
        "max_output_tokens": "Maximum number of tokens the model can generate in a single response",
        "supports_extended_thinking": "Whether the model supports extended reasoning tokens",
        "supports_json_mode": "Whether the model can guarantee valid JSON output",
        "supports_function_calling": "Whether the model supports function/tool calling",
        "supports_images": "Whether the model can process images/visual input",
        "max_image_size_mb": "Maximum total size in MB for all images combined (capped at 40MB max for custom models)",
        "supports_temperature": "Whether the model accepts temperature parameter in API calls (set to false for O3/O4 reasoning models)",
        "temperature_constraint": "Type of temperature constraint: 'fixed' (fixed value), 'range' (continuous range), 'discrete' (specific values), or omit for default range",
        "description": "Human-readable description of the model",
        "intelligence_score": "1-20 human rating used as the primary signal for auto-mode model ordering",
        "allow_code_generation": "Whether this model can generate and suggest fully working code",
    },
}


@dataclass
class CopilotModel:
    """Minimal model representation returned by the proxy."""

    model_id: str
    display_name: str
    owned_by: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> CopilotModel | None:
        model_id = payload.get("id")
        if not isinstance(model_id, str):
            return None

        display_name = payload.get("display_name") or model_id
        owned_by = payload.get("owned_by") or "github-copilot"
        return cls(model_id=model_id, display_name=display_name, owned_by=owned_by)


def slugify(value: str) -> str:
    slug = ALIAS_SANITISE_PATTERN.sub("-", value.lower()).strip("-")
    return slug or "model"


def is_current_chat_model(model: CopilotModel) -> bool:
    """Return whether a Copilot model should be exposed for chat generation."""

    base = model.model_id.lower()
    if base in OUTDATED_COPILOT_MODEL_IDS:
        return False

    if any(base.startswith(prefix) for prefix in OUTDATED_COPILOT_MODEL_PREFIXES):
        return False

    return True


def infer_capabilities(model_id: str) -> dict[str, Any]:
    """Best-effort capability approximation for Copilot models."""

    base = model_id.lower()

    context_window = 128_000
    max_output = 4_096
    intelligence = 12
    supports_images = False
    supports_function_calling = True
    supports_json_mode = True
    supports_extended_thinking = False
    supports_temperature = True
    allow_code_generation = False

    # GPT-5.4 series - latest flagship generation
    if "gpt-5.4" in base or "gpt5.4" in base:
        context_window = 500_000
        max_output = 150_000
        intelligence = 20
        supports_images = True
        supports_extended_thinking = True
        supports_function_calling = True
        allow_code_generation = True
        if "pro" in base:
            intelligence = 20
            max_output = 300_000
        elif "mini" in base:
            intelligence = 18

    # GPT-5.3 Codex - latest Codex-optimized agentic coding model
    elif "gpt-5.3-codex" in base or "gpt5.3codex" in base:
        context_window = 400_000
        max_output = 128_000
        intelligence = 19
        supports_images = True
        supports_extended_thinking = True
        supports_function_calling = True
        allow_code_generation = True

    # O3/O4 reasoning models
    elif "o3-pro" in base or "o3pro" in base:
        context_window = 200_000
        max_output = 65_536
        supports_extended_thinking = False
        supports_temperature = False
        supports_images = True
        intelligence = 16

    elif "o4-mini" in base or "o4mini" in base or "o4" in base:
        context_window = 200_000
        max_output = 65_536
        supports_extended_thinking = False
        supports_temperature = False
        supports_images = True
        intelligence = 13

    # Claude Opus 4.6 - latest flagship
    elif "opus" in base or "claude-opus" in base:
        context_window = 1_000_000
        max_output = 128_000
        supports_images = True
        supports_extended_thinking = True
        supports_function_calling = True
        intelligence = 20
        allow_code_generation = True

    # Claude Sonnet 4.6 - latest balanced Claude
    elif "sonnet" in base or "claude-sonnet" in base:
        context_window = 1_000_000
        max_output = 64_000
        supports_images = True
        supports_extended_thinking = True
        supports_function_calling = True
        intelligence = 19
        allow_code_generation = True

    # Claude Haiku 4.5 - fast model
    elif "haiku" in base or "claude-haiku" in base:
        context_window = 200_000
        max_output = 64_000
        supports_images = True
        supports_extended_thinking = True
        supports_function_calling = True
        intelligence = 14

    # Gemini 3/3.1 - latest Google generation
    elif "gemini-3" in base or "gemini3" in base:
        context_window = 1_048_576
        max_output = 65_536
        supports_images = True
        supports_function_calling = True
        supports_extended_thinking = True
        intelligence = 13 if "flash" in base else 20
        allow_code_generation = True

    # Gemini 2.5 series
    elif "gemini" in base:
        context_window = 1_048_576
        max_output = 65_536
        supports_images = True
        supports_function_calling = True
        if "pro" in base:
            supports_extended_thinking = True
            intelligence = 18
            allow_code_generation = True
        elif "flash" in base:
            supports_extended_thinking = True
            intelligence = 12
        else:
            supports_extended_thinking = True
            intelligence = 16

    # Grok 4 - latest (2M context)
    elif "grok" in base:
        context_window = 2_000_000
        max_output = 256_000
        supports_images = True
        supports_extended_thinking = True
        supports_function_calling = True
        intelligence = 18
        allow_code_generation = True
        if "code" in base or "fast" in base:
            intelligence = 15
            supports_extended_thinking = False

    # MiniMax M2.5 and Copilot internal routers
    elif "minimax" in base or base.startswith("accounts/msft/routers/"):
        context_window = 262_144
        max_output = 65_536
        supports_images = False
        supports_extended_thinking = False
        supports_function_calling = True
        intelligence = 16 if "minimax" in base else 10
        allow_code_generation = "minimax" in base

    # Copilot-internal coding assistants
    elif base.startswith("oswe-vscode") or "goldeneye" in base:
        context_window = 128_000
        max_output = 65_536
        supports_images = False
        supports_extended_thinking = False
        supports_function_calling = True
        intelligence = 13
        allow_code_generation = True

    # Llama 4 series
    elif "llama-4" in base or "llama4" in base:
        context_window = 1_048_576
        max_output = 65_536
        supports_images = True
        supports_function_calling = True
        supports_extended_thinking = True
        intelligence = 16

    # DeepSeek R1
    elif "deepseek" in base:
        context_window = 65_536
        max_output = 32_768
        supports_images = False
        if "r1" in base:
            supports_extended_thinking = True
            intelligence = 15
        else:
            supports_extended_thinking = False
            intelligence = 12

    # Mistral
    elif "mistral" in base:
        context_window = 128_000
        max_output = 32_000
        supports_images = False
        intelligence = 12

    # Qwen
    elif "qwen" in base:
        context_window = 32_768
        max_output = 16_384
        supports_images = False
        if "coder" in base:
            intelligence = 12
        else:
            intelligence = 10

    max_image_size = 40.0 if supports_images else 0.0

    result = {
        "context_window": context_window,
        "max_output_tokens": max_output,
        "supports_extended_thinking": supports_extended_thinking,
        "supports_function_calling": supports_function_calling,
        "supports_json_mode": supports_json_mode,
        "supports_images": supports_images,
        "supports_temperature": supports_temperature,
        "max_image_size_mb": max_image_size,
        "intelligence_score": intelligence,
    }

    if allow_code_generation:
        result["allow_code_generation"] = True

    return result


def coerce_aliases(value: Any) -> list[str]:
    """Normalize aliases from an existing registry entry."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [alias for alias in value if isinstance(alias, str)]
    return []


def build_aliases(
    prefix: str, model: CopilotModel, used_aliases: set[str], existing_aliases: Iterable[str] = ()
) -> list[str]:
    raw = f"{prefix}/{model.model_id}"
    slug_alias = f"{prefix}/{slugify(model.model_id)}"

    candidates = [raw, slug_alias]

    display_slug = slugify(model.display_name)
    display_alias = f"{prefix}/{display_slug}"
    if display_alias not in candidates:
        candidates.append(display_alias)

    for semantic_alias in SEMANTIC_COPILOT_ALIASES.get(model.model_id, []):
        candidates.append(f"{prefix}/{semantic_alias}")

    for existing_alias in existing_aliases:
        if existing_alias.startswith(f"{prefix}/"):
            candidates.append(existing_alias)

    aliases: list[str] = []

    for alias in candidates:
        lowered = alias.lower()
        if lowered in used_aliases:
            continue
        aliases.append(alias)
        used_aliases.add(lowered)

    if not aliases:
        base = f"{prefix}/{slugify(model.model_id)}"
        candidate = base or f"{prefix}/model"
        counter = 2
        while candidate.lower() in used_aliases:
            candidate = f"{base}-{counter}"
            counter += 1
        aliases.append(candidate)
        used_aliases.add(candidate.lower())

    return aliases


def build_entry(
    prefix: str,
    model: CopilotModel,
    used_aliases: set[str],
    existing_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    capabilities = infer_capabilities(model.model_id)
    existing_aliases = coerce_aliases(existing_entry.get("aliases")) if existing_entry else []
    aliases = build_aliases(prefix, model, used_aliases, existing_aliases)

    description = f"{model.display_name} via GitHub Copilot proxy (vendor: {model.owned_by})."

    entry: dict[str, Any] = {
        "model_name": model.model_id,
        "friendly_name": f"{model.display_name} (Copilot)",
        "aliases": aliases,
        "description": description,
        **capabilities,
    }

    return entry


def fetch_models(base_url: str, api_key: str | None, timeout: int) -> list[CopilotModel]:
    url = f"{base_url.rstrip('/')}/models"
    headers = {"accept": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    req = request.Request(url, headers=headers)

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Unexpected status {resp.status} from {url}")
            payload = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"HTTP error from {url}: {exc.code} {exc.reason}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to reach {url}: {exc.reason}") from exc

    models: list[CopilotModel] = []
    for raw in payload.get("data", []):
        if not isinstance(raw, dict):
            continue
        model = CopilotModel.from_payload(raw)
        if model:
            models.append(model)

    return models


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"models": []}

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse {path}: {exc}") from exc


def retain_non_copilot_entries(models: Iterable[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    retained: list[dict[str, Any]] = []
    marker = f"{prefix}/"

    for entry in models:
        aliases = entry.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]

        if any(isinstance(alias, str) and alias.startswith(marker) for alias in aliases):
            continue

        retained.append(entry)

    return retained


def existing_copilot_entries_by_model(models: Iterable[dict[str, Any]], prefix: str) -> dict[str, dict[str, Any]]:
    """Return existing Copilot-managed entries keyed by model name."""

    existing: dict[str, dict[str, Any]] = {}
    marker = f"{prefix}/"

    for entry in models:
        model_name = entry.get("model_name")
        if not isinstance(model_name, str):
            continue

        aliases = coerce_aliases(entry.get("aliases"))
        if any(alias.startswith(marker) for alias in aliases):
            existing[model_name] = entry

    return existing


def save_registry(path: Path, data: dict[str, Any], dry_run: bool) -> None:
    formatted = json.dumps(data, indent=2, ensure_ascii=True) + "\n"
    if dry_run:
        sys.stdout.write(formatted)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(formatted)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronise GitHub Copilot models into the custom registry.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("CUSTOM_API_URL", DEFAULT_BASE_URL),
        help="Base URL for the OpenAI-compatible endpoint (default: %(default)s)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("CUSTOM_API_KEY"),
        help="API key for the endpoint (falls back to CUSTOM_API_KEY)",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "conf" / "custom_models.json"),
        help="Path to the target custom model registry file.",
    )
    parser.add_argument(
        "--alias-prefix",
        default=DEFAULT_ALIAS_PREFIX,
        help="Alias prefix to use for generated entries.",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated JSON instead of writing to disk.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        models = fetch_models(args.base_url, args.api_key, args.timeout)
    except Exception as exc:  # noqa: BLE001 - surface useful error message
        print(f"[sync-copilot-models] {exc}", file=sys.stderr)
        return 1

    if not models:
        print(
            "[sync-copilot-models] No models discovered from the proxy.",
            file=sys.stderr,
        )
        return 1

    output_path = Path(args.output).expanduser()
    registry = load_registry(output_path)

    readme_block = registry.get("_README") or DEFAULT_README
    existing_models = registry.get("models", [])
    retained = retain_non_copilot_entries(existing_models, args.alias_prefix)
    existing_copilot_entries = existing_copilot_entries_by_model(existing_models, args.alias_prefix)

    used_aliases: set[str] = set()
    current_models = [model for model in models if is_current_chat_model(model)]
    generated = [
        build_entry(args.alias_prefix, model, used_aliases, existing_copilot_entries.get(model.model_id))
        for model in current_models
    ]
    generated.sort(
        key=lambda entry: (
            -entry.get("intelligence_score", 0),
            entry.get("friendly_name", ""),
        )
    )

    registry_payload = {"_README": readme_block, "models": retained + generated}

    save_registry(output_path, registry_payload, args.dry_run)
    print(
        f"[sync-copilot-models] Wrote {len(generated)} Copilot models to {output_path} "
        f"(retained {len(retained)} entries, skipped {len(models) - len(current_models)} outdated/non-chat models)."
    )

    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
