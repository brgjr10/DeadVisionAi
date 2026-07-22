"""
LM Studio provider adapter.
OpenAI-compatible local inference via LM Studio.
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
    token_usage_total,
)
from app.providers.base import ProviderBase

logger = get_logger(__name__)


class LMStudioProvider(ProviderBase):
    """
    Provider implementation for LM Studio local models.
    Uses OpenAI-compatible API endpoint.
    """

    def __init__(
        self,
        provider_id: str,
        model_id: str,
        base_url: str,
        api_key: str = "lm-studio",
    ) -> None:
        super().__init__(provider_id, model_id)
        # Normalise: strip trailing slash and /v1 suffix so we always resolve
        # to the canonical OpenAI-compatible path: {base}/v1/chat/completions
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            normalized = normalized[:-3]
        self._base_url = normalized
        self._api_key = api_key

    async def complete(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Send messages to LM Studio and return the completion."""
        if stream:
            return self._stream_complete(messages)
        return await self._full_complete(messages)

    async def _full_complete(self, messages: list[dict]) -> str:
        """Non-streaming completion."""
        start = time.perf_counter()
        url = f"{self._base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            latency_ms = (time.perf_counter() - start) * 1000
            tokens = data.get("usage", {}).get("total_tokens", 0)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

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
            logger.error("lmstudio_completion_error", error=str(exc))
            raise

    async def _stream_complete(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Streaming completion — yields string chunks as they arrive."""
        start = time.perf_counter()
        url = f"{self._base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": True,
        }

        total_tokens = 0
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                import json
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if delta:
                                    total_tokens += 1
                                    yield delta
                            except Exception:
                                continue

            latency_ms = (time.perf_counter() - start) * 1000
            self._record_success(total_tokens, latency_ms)
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
            logger.error("lmstudio_stream_error", error=str(exc))
            raise

    async def health_check(self) -> bool:
        """
        Probe the LM Studio server:
        1. GET /v1/models  → confirms server is up and model list loads
        2. POST /v1/chat/completions with max_tokens=1 → confirms inference works
        """
        base = self._base_url
        try:
            # Step 1 — model list
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    f"{base}/v1/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                if r.status_code != 200:
                    return False

            # Step 2 — lightweight inference probe
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.post(
                    f"{base}/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                    },
                    json={
                        "model": self.model_id,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                    },
                )
                return r.status_code == 200
        except Exception:
            return False