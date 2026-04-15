"""
Shodan tool - query the Shodan search engine for internet-connected devices.

Provides four capabilities:
- search_shodan: text search across Shodan's index
- get_host_info: full host/IP details
- get_ssl_info: SSL certificate info for a hostname
- scan_network_range: submit an on-demand scan for a CIDR range

Requires SHODAN_API_KEY environment variable.
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


SHODAN_API_BASE = "https://api.shodan.io"

SHODAN_FIELD_DESCRIPTIONS = {
    "action": (
        "Action to perform. One of: search_shodan, get_host_info, get_ssl_info, scan_network_range."
    ),
    "query": "Shodan search query (e.g. 'apache port:80 country:US'). Required for search_shodan.",
    "limit": "Maximum number of results to return for search_shodan (default: 10, max: 100).",
    "ip": "IP address to look up. Required for get_host_info.",
    "hostname": "Hostname to check SSL certificate for. Required for get_ssl_info.",
    "cidr": "CIDR network range to scan (e.g. '192.168.1.0/24'). Required for scan_network_range.",
}


class ShodanRequest(ToolRequest):
    action: str = Field(..., description=SHODAN_FIELD_DESCRIPTIONS["action"])
    query: str | None = Field(None, description=SHODAN_FIELD_DESCRIPTIONS["query"])
    limit: int = Field(10, description=SHODAN_FIELD_DESCRIPTIONS["limit"])
    ip: str | None = Field(None, description=SHODAN_FIELD_DESCRIPTIONS["ip"])
    hostname: str | None = Field(None, description=SHODAN_FIELD_DESCRIPTIONS["hostname"])
    cidr: str | None = Field(None, description=SHODAN_FIELD_DESCRIPTIONS["cidr"])


class ShodanTool(SimpleTool):
    """Query Shodan's internet-wide scan data without routing through an AI model."""

    def get_name(self) -> str:
        return "shodan"

    def get_description(self) -> str:
        return (
            "Query the Shodan search engine for internet-connected device information. "
            "Supports text search, host/IP lookup, SSL certificate inspection, and on-demand network scanning. "
            "Requires SHODAN_API_KEY environment variable."
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
        return ShodanRequest

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        return {
            "action": {"type": "string", "description": SHODAN_FIELD_DESCRIPTIONS["action"]},
            "query": {"type": "string", "description": SHODAN_FIELD_DESCRIPTIONS["query"]},
            "limit": {"type": "integer", "description": SHODAN_FIELD_DESCRIPTIONS["limit"]},
            "ip": {"type": "string", "description": SHODAN_FIELD_DESCRIPTIONS["ip"]},
            "hostname": {"type": "string", "description": SHODAN_FIELD_DESCRIPTIONS["hostname"]},
            "cidr": {"type": "string", "description": SHODAN_FIELD_DESCRIPTIONS["cidr"]},
        }

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search_shodan", "get_host_info", "get_ssl_info", "scan_network_range"],
                    "description": SHODAN_FIELD_DESCRIPTIONS["action"],
                },
                "query": {"type": "string", "description": SHODAN_FIELD_DESCRIPTIONS["query"]},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": SHODAN_FIELD_DESCRIPTIONS["limit"],
                },
                "ip": {"type": "string", "description": SHODAN_FIELD_DESCRIPTIONS["ip"]},
                "hostname": {"type": "string", "description": SHODAN_FIELD_DESCRIPTIONS["hostname"]},
                "cidr": {"type": "string", "description": SHODAN_FIELD_DESCRIPTIONS["cidr"]},
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

            api_key = os.environ.get("SHODAN_API_KEY", "").strip()
            if not api_key:
                result = {
                    "status": "error",
                    "error": "SHODAN_API_KEY environment variable is not set.",
                }
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

            action = request.action
            if action == "search_shodan":
                result = await self._search_shodan(api_key, request.query, request.limit)
            elif action == "get_host_info":
                result = await self._get_host_info(api_key, request.ip)
            elif action == "get_ssl_info":
                result = await self._get_ssl_info(api_key, request.hostname)
            elif action == "scan_network_range":
                result = await self._scan_network_range(api_key, request.cidr)
            else:
                result = {
                    "status": "error",
                    "error": f"Unknown action '{action}'. Valid actions: search_shodan, get_host_info, get_ssl_info, scan_network_range.",
                }

            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        except Exception as e:
            logger.error(f"Error in shodan tool: {e}", exc_info=True)
            error = {"status": "error", "error": str(e)}
            return [TextContent(type="text", text=json.dumps(error, ensure_ascii=False, indent=2))]

    async def _search_shodan(self, api_key: str, query: str | None, limit: int) -> dict:
        import httpx

        if not query:
            return {"status": "error", "error": "query is required for search_shodan."}

        params = {"key": api_key, "query": query, "minify": True}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{SHODAN_API_BASE}/shodan/host/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        matches = data.get("matches", [])[:limit]
        return {
            "status": "success",
            "action": "search_shodan",
            "query": query,
            "total": data.get("total", 0),
            "returned": len(matches),
            "matches": matches,
        }

    async def _get_host_info(self, api_key: str, ip: str | None) -> dict:
        import httpx

        if not ip:
            return {"status": "error", "error": "ip is required for get_host_info."}

        params = {"key": api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{SHODAN_API_BASE}/shodan/host/{ip}", params=params)
            resp.raise_for_status()
            data = resp.json()

        return {"status": "success", "action": "get_host_info", "ip": ip, "data": data}

    async def _get_ssl_info(self, api_key: str, hostname: str | None) -> dict:
        import httpx

        if not hostname:
            return {"status": "error", "error": "hostname is required for get_ssl_info."}

        # Shodan SSL search: query ssl.cert.subject.cn for the hostname
        params = {"key": api_key, "query": f"ssl.cert.subject.cn:{hostname}", "minify": True}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{SHODAN_API_BASE}/shodan/host/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        matches = data.get("matches", [])
        ssl_entries = []
        for match in matches:
            ssl = match.get("ssl", {})
            if ssl:
                ssl_entries.append(
                    {
                        "ip": match.get("ip_str"),
                        "port": match.get("port"),
                        "subject": ssl.get("cert", {}).get("subject", {}),
                        "issuer": ssl.get("cert", {}).get("issuer", {}),
                        "expires": ssl.get("cert", {}).get("expires"),
                        "issued": ssl.get("cert", {}).get("issued"),
                        "fingerprint": ssl.get("cert", {}).get("fingerprint", {}),
                    }
                )

        return {
            "status": "success",
            "action": "get_ssl_info",
            "hostname": hostname,
            "total": data.get("total", 0),
            "ssl_entries": ssl_entries,
        }

    async def _scan_network_range(self, api_key: str, cidr: str | None) -> dict:
        import httpx

        if not cidr:
            return {"status": "error", "error": "cidr is required for scan_network_range."}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{SHODAN_API_BASE}/shodan/scan",
                params={"key": api_key},
                data={"ips": cidr},
            )
            resp.raise_for_status()
            data = resp.json()

        return {"status": "success", "action": "scan_network_range", "cidr": cidr, "data": data}
