"""
Optional disk persistence for conversation transcripts.

This module complements the in-memory continuation system by writing per-thread
snapshots to disk when explicitly enabled. It is intended for local inspection
and debugging, not as a replacement for the active conversation storage used by
the MCP server.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any

from utils.env import get_env, get_env_bool

if TYPE_CHECKING:
    from utils.conversation_memory import ThreadContext

logger = logging.getLogger(__name__)

_DEFAULT_TRANSCRIPTS_DIR = Path(__file__).resolve().parent.parent / "logs" / "conversations"


def transcripts_enabled() -> bool:
    """Return True when transcript persistence is enabled."""
    return get_env_bool("CONVERSATION_TRANSCRIPTS_ENABLED", False)


def get_transcripts_dir() -> Path:
    """Resolve the transcript output directory."""
    configured_dir = get_env("CONVERSATION_TRANSCRIPTS_DIR")
    if configured_dir:
        return Path(configured_dir).expanduser()
    return _DEFAULT_TRANSCRIPTS_DIR


def persist_thread_snapshot(context: "ThreadContext", event: str) -> None:
    """
    Write a thread snapshot to disk when transcript persistence is enabled.

    Generates:
    - `<thread_id>.json` complete machine-readable snapshot
    - `<thread_id>.md` human-readable transcript
    - `index.jsonl` append-only activity index for recent thread lookup
    """
    if not transcripts_enabled():
        return

    try:
        transcripts_dir = get_transcripts_dir()
        transcripts_dir.mkdir(parents=True, exist_ok=True)

        payload = context.model_dump(mode="json")
        payload["event"] = event
        payload["turn_count"] = len(context.turns)
        payload["persisted_at"] = datetime.now(timezone.utc).isoformat()

        json_path = transcripts_dir / f"{context.thread_id}.json"
        markdown_path = transcripts_dir / f"{context.thread_id}.md"
        index_path = transcripts_dir / "index.jsonl"

        _atomic_write_text(json_path, json.dumps(payload, indent=2, sort_keys=True))
        _atomic_write_text(markdown_path, _render_markdown_transcript(context, event))
        _append_index_record(index_path, context, event)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to persist transcript for thread %s: %s", context.thread_id, exc)


def _append_index_record(index_path: Path, context: "ThreadContext", event: str) -> None:
    latest_turn = context.turns[-1] if context.turns else None
    record: dict[str, Any] = {
        "thread_id": context.thread_id,
        "parent_thread_id": context.parent_thread_id,
        "event": event,
        "tool_name": context.tool_name,
        "turn_count": len(context.turns),
        "created_at": context.created_at,
        "last_updated_at": context.last_updated_at,
        "persisted_at": datetime.now(timezone.utc).isoformat(),
    }
    if latest_turn is not None:
        record["latest_role"] = latest_turn.role
        record["latest_tool_name"] = latest_turn.tool_name
        record["latest_model_name"] = latest_turn.model_name
        record["latest_timestamp"] = latest_turn.timestamp

    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")


def _render_markdown_transcript(context: "ThreadContext", event: str) -> str:
    lines = [
        "# Zen Conversation Transcript",
        "",
        f"- Thread ID: `{context.thread_id}`",
        f"- Parent Thread ID: `{context.parent_thread_id or 'none'}`",
        f"- Tool: `{context.tool_name}`",
        f"- Created At: `{context.created_at}`",
        f"- Last Updated At: `{context.last_updated_at}`",
        f"- Persisted Event: `{event}`",
        f"- Turn Count: `{len(context.turns)}`",
        "",
        "## Initial Context",
        "",
        "```json",
        json.dumps(context.initial_context, indent=2, sort_keys=True),
        "```",
        "",
        "## Turns",
        "",
    ]

    if not context.turns:
        lines.append("_No turns recorded yet._")
        lines.append("")
        return "\n".join(lines)

    for index, turn in enumerate(context.turns, start=1):
        lines.extend(
            [
                f"### Turn {index}",
                "",
                f"- Role: `{turn.role}`",
                f"- Timestamp: `{turn.timestamp}`",
                f"- Tool: `{turn.tool_name or 'unknown'}`",
                f"- Model Provider: `{turn.model_provider or 'unknown'}`",
                f"- Model Name: `{turn.model_name or 'unknown'}`",
                f"- Files: `{', '.join(turn.files or []) or 'none'}`",
                f"- Images: `{', '.join(turn.images or []) or 'none'}`",
                "",
                "````text",
                turn.content.rstrip(),
                "````",
                "",
            ]
        )

    return "\n".join(lines)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_name = handle.name
    os.replace(temp_name, path)
