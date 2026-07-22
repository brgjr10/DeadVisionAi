"""
SearXNG provider adapter.
Self-hosted search aggregator — always free, no API key required.
Treated as a tool provider (search-type tasks), not a text-generation provider.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.observability.logging_config import get_logger
from app.observability.metrics import (
    provider_latency_seconds,
    provider_requests_total,
)
from app.providers.base import ProviderBase

logger = get_logger(__name__)


class SearXNGProvider(ProviderBase):
    """
    Provider implementation for a self-hosted SearXNG instance.
    Exposes search as an LLM-style 'complete' call: the prompt is treated as
    a search query and the top N results are returned as a concatenated string.
    Heavily scored as cost=0, low latency, routing preference for tool-flagged tasks.
    """

    COST_PER_TOKEN = 0.0  # always free — self-hosted

    def __init__(self, provider_id: str = "searxng") -> None:
        super().__init__(provider_id, "searxng/search")
        self._settings = get_settings()

    # ── ProviderBase interface ────────────────────────────────────────────

    async def complete(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> str:
        """Run a search query and return top results as plain text."""
        query = messages[-1]["content"] if messages else ""
        start = time.perf_counter()

        try:
            results = await self._search(query, max_results=5)
            latency_ms = (time.perf_counter() - start) * 1000
            self._record_success(len(query.split()), latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status="success",
            ).inc()
            provider_latency_seconds.labels(provider_id=self.provider_id).observe(
                latency_ms / 1000
            )
            return results
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self._record_error(latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status="error",
            ).inc()
            logger.error("searxng_search_error", error=str(exc))
            raise

    async def health_check(self) -> bool:
        """Probe the SearXNG /healthz or / endpoint with a short timeout."""
        base_url = self._settings.searxng_base_url.rstrip("/")
        for path in ("/healthz", "/", "/search"):
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{base_url}{path}")
                    if resp.status_code == 200:
                        return True
            except Exception:
                continue
        return False

    # ── Internal helpers ───────────────────────────────────────────────────

    async def _search(self, query: str, max_results: int = 5) -> str:
        """Call SearXNG /search and return a plain-text summary of results."""
        base_url = self._settings.searxng_base_url.rstrip("/")
        timeout = float(getattr(self._settings, "search_timeout_seconds", 10))

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "safesearch": "0",
                },
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        parts: list[str] = []
        for r in data.get("results", [])[:max_results]:
            title = r.get("title", "")
            snippet = r.get("content") or r.get("description", "")
            url = r.get("url", "")
            if title and snippet:
                parts.append(f"{title}: {snippet} ({url})")
            elif snippet:
                parts.append(f"{snippet} ({url})")

        return "\n".join(parts) if parts else "(no results)"
