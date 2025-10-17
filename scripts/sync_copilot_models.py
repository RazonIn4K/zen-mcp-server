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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib import error, request


DEFAULT_BASE_URL = "http://localhost:4141/v1"
DEFAULT_ALIAS_PREFIX = "copilot"
DEFAULT_TIMEOUT = 15

ALIAS_SANITISE_PATTERN = re.compile(r"[^a-z0-9]+")

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
    },
}


@dataclass
class CopilotModel:
    """Minimal model representation returned by the proxy."""

    model_id: str
    display_name: str
    owned_by: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CopilotModel | None":
        model_id = payload.get("id")
        if not isinstance(model_id, str):
            return None

        display_name = payload.get("display_name") or model_id
        owned_by = payload.get("owned_by") or "github-copilot"
        return cls(model_id=model_id, display_name=display_name, owned_by=owned_by)


def slugify(value: str) -> str:
    slug = ALIAS_SANITISE_PATTERN.sub("-", value.lower()).strip("-")
    return slug or "model"


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

    if any(token in base for token in ("gpt-4.1", "gpt-4o", "o4")):
        context_window = 128_000
        max_output = 8_192
        intelligence = 17 if "mini" not in base else 14
        supports_images = True
        supports_extended_thinking = True

    if "o1" in base or "o3" in base:
        supports_extended_thinking = True
        supports_temperature = False

    if "o4" in base:
        supports_temperature = False

    if "gpt-4o-mini" in base or "mini" in base:
        intelligence = min(intelligence, 13)
        supports_extended_thinking = False
        max_output = 6_144 if "o4" in base else 4_096
        supports_images = True

    if "gpt-3.5" in base:
        context_window = 16_384
        max_output = 2_048
        intelligence = 9
        supports_images = False
        supports_extended_thinking = False

    if "claude" in base:
        context_window = 200_000
        max_output = 8_192
        supports_images = True
        supports_extended_thinking = "sonnet" in base or "opus" in base
        intelligence = 16 if supports_extended_thinking else 13

    if "haiku" in base:
        intelligence = 12
        supports_extended_thinking = False
        max_output = 6_000

    if "gemini" in base:
        context_window = 1_048_576
        max_output = 8_192
        supports_images = True
        supports_extended_thinking = "pro" in base
        intelligence = 16 if supports_extended_thinking else 13

    max_image_size = 40.0 if supports_images else 0.0

    return {
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


def build_aliases(prefix: str, model: CopilotModel) -> list[str]:
    raw = f"{prefix}/{model.model_id}"
    slug_alias = f"{prefix}/{slugify(model.model_id)}"
    candidates = {raw.lower(): raw, slug_alias.lower(): slug_alias}

    display_slug = slugify(model.display_name)
    display_alias = f"{prefix}/{display_slug}"
    candidates.setdefault(display_alias.lower(), display_alias)

    return list(candidates.values())


def build_entry(prefix: str, model: CopilotModel) -> dict[str, Any]:
    capabilities = infer_capabilities(model.model_id)
    aliases = build_aliases(prefix, model)

    description = (
        f"{model.display_name} via GitHub Copilot proxy "
        f"(vendor: {model.owned_by}, synced {datetime.now(timezone.utc).date().isoformat()})."
    )

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
    retained = retain_non_copilot_entries(registry.get("models", []), args.alias_prefix)

    generated = [build_entry(args.alias_prefix, model) for model in models]
    generated.sort(
        key=lambda entry: (
            -entry.get("intelligence_score", 0),
            entry.get("friendly_name", ""),
        )
    )

    registry_payload = {"_README": readme_block, "models": retained + generated}

    save_registry(output_path, registry_payload, args.dry_run)
    print(
        f"[sync-copilot-models] Wrote {len(generated)} Copilot models to {output_path} (retained {len(retained)} entries)."
    )

    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
