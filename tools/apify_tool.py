"""
Apify tool - interact with the Apify platform to run actors and retrieve results.

Provides four capabilities:
- run_actor: start an Apify actor with custom input
- get_actor_run: poll the status and output of a run
- get_dataset_items: retrieve structured dataset items directly
- search_actors: search the Apify actor store

`search_actors` works anonymously. `run_actor`, `get_actor_run`, and
`get_dataset_items` require `APIFY_API_TOKEN`.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from pydantic import Field

from config import TEMPERATURE_ANALYTICAL
from tools.shared.base_models import ToolRequest
from tools.simple.base import SimpleTool

if TYPE_CHECKING:
    from tools.models import ToolModelCategory


APIFY_API_BASE = "https://api.apify.com/v2"

APIFY_FIELD_DESCRIPTIONS = {
    "action": "Action to perform. One of: run_actor, get_actor_run, get_dataset_items, search_actors.",
    "actor_id": (
        "Actor ID or name in 'username~actor-name' format (e.g. 'apify~web-scraper'). "
        "Required for run_actor."
    ),
    "input_data": "JSON input object to pass to the actor. Required for run_actor.",
    "run_id": "Run ID returned by run_actor. Required for get_actor_run.",
    "dataset_id": "Dataset ID returned by run_actor or get_actor_run. Required for get_dataset_items.",
    "limit": "Maximum number of dataset items to return (default: 10, max: 100).",
    "query": "Search term for finding actors in the Apify store. Required for search_actors.",
}


class ApifyRequest(ToolRequest):
    action: str = Field(..., description=APIFY_FIELD_DESCRIPTIONS["action"])
    actor_id: str | None = Field(None, description=APIFY_FIELD_DESCRIPTIONS["actor_id"])
    input_data: dict | None = Field(None, description=APIFY_FIELD_DESCRIPTIONS["input_data"])
    run_id: str | None = Field(None, description=APIFY_FIELD_DESCRIPTIONS["run_id"])
    dataset_id: str | None = Field(None, description=APIFY_FIELD_DESCRIPTIONS["dataset_id"])
    limit: int = Field(10, description=APIFY_FIELD_DESCRIPTIONS["limit"])
    query: str | None = Field(None, description=APIFY_FIELD_DESCRIPTIONS["query"])


class ApifyTool(SimpleTool):
    """Interact with the Apify platform to run web-scraping actors without routing through an AI model."""

    def get_name(self) -> str:
        return "apify"

    def get_description(self) -> str:
        return (
            "Interact with the Apify platform to run web-scraping and automation actors, "
            "retrieve run results, fetch dataset items, and search the actor store. "
            "Searching the actor store works anonymously; running actors requires APIFY_API_TOKEN."
        )

    def get_system_prompt(self) -> str:
        return ""

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def requires_model(self) -> bool:
        return False

    def get_model_category(self) -> ToolModelCategory:
        from tools.models import ToolModelCategory

        return ToolModelCategory.FAST_RESPONSE

    def get_request_model(self):
        return ApifyRequest

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        return {
            "action": {"type": "string", "description": APIFY_FIELD_DESCRIPTIONS["action"]},
            "actor_id": {"type": "string", "description": APIFY_FIELD_DESCRIPTIONS["actor_id"]},
            "input_data": {"type": "object", "description": APIFY_FIELD_DESCRIPTIONS["input_data"]},
            "run_id": {"type": "string", "description": APIFY_FIELD_DESCRIPTIONS["run_id"]},
            "dataset_id": {"type": "string", "description": APIFY_FIELD_DESCRIPTIONS["dataset_id"]},
            "limit": {"type": "integer", "description": APIFY_FIELD_DESCRIPTIONS["limit"]},
            "query": {"type": "string", "description": APIFY_FIELD_DESCRIPTIONS["query"]},
        }

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["run_actor", "get_actor_run", "get_dataset_items", "search_actors"],
                    "description": APIFY_FIELD_DESCRIPTIONS["action"],
                },
                "actor_id": {"type": "string", "description": APIFY_FIELD_DESCRIPTIONS["actor_id"]},
                "input_data": {
                    "type": "object",
                    "description": APIFY_FIELD_DESCRIPTIONS["input_data"],
                },
                "run_id": {"type": "string", "description": APIFY_FIELD_DESCRIPTIONS["run_id"]},
                "dataset_id": {"type": "string", "description": APIFY_FIELD_DESCRIPTIONS["dataset_id"]},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": APIFY_FIELD_DESCRIPTIONS["limit"],
                },
                "query": {"type": "string", "description": APIFY_FIELD_DESCRIPTIONS["query"]},
            },
            "required": ["action"],
        }

    async def prepare_prompt(self, request) -> str:  # pragma: no cover - not used
        return ""

    def format_response(self, response: str, request, model_info: dict | None = None) -> str:
        return response

    async def execute(self, arguments: dict[str, Any]) -> list:
        import logging

        from mcp.types import TextContent

        logger = logging.getLogger(__name__)

        try:
            request = self.get_request_model()(**arguments)

            api_token = os.environ.get("APIFY_API_TOKEN", "").strip()
            action = request.action

            if action in {"run_actor", "get_actor_run", "get_dataset_items"} and not api_token:
                result = {
                    "status": "error",
                    "error": "APIFY_API_TOKEN environment variable is not set.",
                    "hint": "Get a free token at https://console.apify.com/account/integrations",
                }
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

            if action == "run_actor":
                result = await self._run_actor(api_token, request.actor_id, request.input_data)
            elif action == "get_actor_run":
                result = await self._get_actor_run(api_token, request.run_id)
            elif action == "get_dataset_items":
                result = await self._get_dataset_items(api_token, request.dataset_id, request.limit)
            elif action == "search_actors":
                result = await self._search_actors(request.query)
            else:
                result = {
                    "status": "error",
                    "error": (
                        f"Unknown action '{action}'. Valid actions: run_actor, get_actor_run, "
                        "get_dataset_items, search_actors."
                    ),
                }

            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        except Exception as e:
            logger.error(f"Error in apify tool: {e}", exc_info=True)
            error = {"status": "error", "error": str(e)}
            return [TextContent(type="text", text=json.dumps(error, ensure_ascii=False, indent=2))]

    async def _run_actor(self, api_token: str, actor_id: str | None, input_data: dict | None) -> dict:
        import httpx

        if not actor_id:
            return {"status": "error", "error": "actor_id is required for run_actor."}
        if input_data is None:
            input_data = {}

        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        url = f"{APIFY_API_BASE}/acts/{actor_id}/runs"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=input_data)
            if resp.status_code == 401:
                return {
                    "status": "error",
                    "error": "APIFY_API_TOKEN is invalid or expired (HTTP 401).",
                    "hint": "Get a valid token at https://console.apify.com/account/integrations",
                }
            resp.raise_for_status()
            data = resp.json()

        run = data.get("data", {})
        return {
            "status": "success",
            "action": "run_actor",
            "actor_id": actor_id,
            "run_id": run.get("id"),
            "run_status": run.get("status"),
            "started_at": run.get("startedAt"),
            "dataset_id": run.get("defaultDatasetId"),
            "data": run,
        }

    async def _get_actor_run(self, api_token: str, run_id: str | None) -> dict:
        import httpx

        if not run_id:
            return {"status": "error", "error": "run_id is required for get_actor_run."}

        headers = {"Authorization": f"Bearer {api_token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            run_resp = await client.get(f"{APIFY_API_BASE}/actor-runs/{run_id}", headers=headers)
            run_resp.raise_for_status()
            run_data = run_resp.json().get("data", {})

        dataset_id = run_data.get("defaultDatasetId")
        output: Any = None
        if run_data.get("status") == "SUCCEEDED" and dataset_id:
            dataset_result = await self._get_dataset_items(api_token, dataset_id, 100)
            if dataset_result.get("status") == "success":
                output = dataset_result.get("items")

        return {
            "status": "success",
            "action": "get_actor_run",
            "run_id": run_id,
            "run_status": run_data.get("status"),
            "started_at": run_data.get("startedAt"),
            "finished_at": run_data.get("finishedAt"),
            "dataset_id": dataset_id,
            "output": output,
            "data": run_data,
        }

    async def _get_dataset_items(self, api_token: str, dataset_id: str | None, limit: int = 10) -> dict:
        import httpx

        if not dataset_id:
            return {"status": "error", "error": "dataset_id is required for get_dataset_items."}

        safe_limit = max(1, min(limit, 100))
        headers = {"Authorization": f"Bearer {api_token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{APIFY_API_BASE}/datasets/{dataset_id}/items",
                headers=headers,
                params={"clean": True, "limit": safe_limit},
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "status": "success",
            "action": "get_dataset_items",
            "dataset_id": dataset_id,
            "returned": len(data) if isinstance(data, list) else 0,
            "items": data,
        }

    async def _search_actors(self, query: str | None) -> dict:
        import httpx

        if not query:
            return {"status": "error", "error": "query is required for search_actors."}

        params = {"search": query, "limit": 10}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{APIFY_API_BASE}/store", params=params)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("data", {}).get("items", [])
        actors = [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "username": a.get("username"),
                "title": a.get("title"),
                "description": a.get("description"),
                "stats": a.get("stats", {}),
            }
            for a in items
        ]
        return {
            "status": "success",
            "action": "search_actors",
            "query": query,
            "total": len(actors),
            "actors": actors,
        }
