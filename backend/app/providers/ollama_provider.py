"""
Ollama provider adapter.
OpenAI-compatible local inference via Ollama.
"""
from __future__ import annotations

import time
from typing import AsyncGenerator, Union

import httpx

from app.config import get_settings
from app.observability.logging_config import get_logger
from app.observability.metrics import (
    provider_latency_seconds,
    provider_requests_total,
)
from app.providers.base import ProviderBase

logger = get_logger(__name__)


class OllamaProvider(ProviderBase):
    """
    Provider implementation for Ollama local models.
    """

    def __init__(
        self,
        provider_id: str,
        model_id: str,
        base_url: str,
    ) -> None:
        super().__init__(provider_id, model_id)
        self._base_url = base_url.rstrip("/")

    async def complete(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Send messages to Ollama and return the completion."""
        if stream:
            return self._stream_complete(messages)
        return await self._full_complete(messages)

    async def _full_complete(self, messages: list[dict]) -> str:
        """Non-streaming completion."""
        start = time.perf_counter()
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            latency_ms = (time.perf_counter() - start) * 1000
            tokens = len(data.get("message", {}).get("content", "").split()) * 2
            content = data.get("message", {}).get("content", "")

            self._record_success(tokens, latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status="success",
            ).inc()
            provider_latency_seconds.labels(provider_id=self.provider_id).observe(
                latency_ms / 1000
            )

            return content

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self._record_error(latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status="error",
            ).inc()
            logger.error("ollama_completion_error", error=str(exc))
            raise

    async def _stream_complete(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Streaming completion via Ollama's /api/generate endpoint."""
        start = time.perf_counter()
        url = f"{self._base_url}/api/generate"
        prompt = messages[-1].get("content", "") if messages else ""
        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                import json
                                data = json.loads(line)
                                response_text = data.get("response", "")
                                if response_text:
                                    yield response_text
                            except Exception:
                                continue

            latency_ms = (time.perf_counter() - start) * 1000
            self._record_success(10, latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status="success",
            ).inc()

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self._record_error(latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status="error",
            ).inc()
            logger.error("ollama_stream_error", error=str(exc))
            raise

    async def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False