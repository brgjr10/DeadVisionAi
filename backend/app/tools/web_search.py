"""
Web search MCP tool.
Queries a search API and returns structured results.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import get_settings
from app.observability.logging_config import get_logger
from app.tools.base import MCPTool, ToolResult

logger = get_logger(__name__)


class WebSearchTool(MCPTool):
    tool_id = "web_search"
    category = "web_search"
    description = "Search the web via SearXNG and return structured results"

    def __init__(self) -> None:
        super().__init__()
        self._settings = get_settings()

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "").strip()
        max_results = int(params.get("max_results", 5))
        start = time.perf_counter()

        if not query:
            return self._timed_result(None, start, exit_status=1, error="No query provided")

        searx_url = self._settings.searxng_base_url.rstrip("/")
        search_url = f"{searx_url}/search"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    search_url,
                    params={
                        "q": query,
                        "format": "json",
                        "safesearch": "0",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for result in data.get("results", [])[:max_results]:
                results.append({
                    "title": result.get("title", ""),
                    "snippet": result.get("content") or result.get("description", ""),
                    "url": result.get("url", ""),
                    "source": result.get("source") or result.get("engine", ""),
                })

            logger.debug(
                "web_search_completed",
                query=query[:50],
                engine="searxng",
                results=len(results),
            )
            return self._timed_result(results, start)

        except Exception as exc:
            logger.error("web_search_error", query=query[:50], engine="searxng", error=str(exc))
            return self._timed_result(None, start, exit_status=1, error=str(exc))
