"""
LiteLLM provider adapter.
Wraps litellm.acompletion for all cloud providers with streaming support,
error classification, and metrics tracking.
"""
from __future__ import annotations

import time
from typing import AsyncGenerator, Union

import litellm
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ServiceUnavailableError,
)

from app.observability.logging_config import get_logger
from app.observability.metrics import (
    provider_latency_seconds,
    provider_requests_total,
    token_usage_total,
)
from app.providers.base import ProviderBase
from app.security.encryption import decrypt_api_key

logger = get_logger(__name__)

# Mapping from provider_id to litellm model prefix and env var name
_PROVIDER_CONFIG: dict[str, dict] = {
    "openrouter": {
        "model_prefix": "openrouter/",
        "api_key_env": "OPENROUTER_API_KEY",
        "api_base": "https://openrouter.ai/api/v1",
        "cost_per_token": 0.0,  # varies by model
    },
    "groq": {
        "model_prefix": "groq/",
        "api_key_env": "GROQ_API_KEY",
        "api_base": None,
        "cost_per_token": 0.0,  # free tier
    },
    "gemini": {
        "model_prefix": "gemini/",
        "api_key_env": "GEMINI_API_KEY",
        "api_base": None,
        "cost_per_token": 0.0,
    },
    "deepseek": {
        "model_prefix": "deepseek/",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_base": None,
        "cost_per_token": 0.000001,
    },
    "together": {
        "model_prefix": "together_ai/",
        "api_key_env": "TOGETHER_API_KEY",
        "api_base": None,
        "cost_per_token": 0.0,
    },
    "fireworks": {
        "model_prefix": "fireworks_ai/",
        "api_key_env": "FIREWORKS_API_KEY",
        "api_base": None,
        "cost_per_token": 0.0,
    },
    "openai": {
        "model_prefix": "openai/",
        "api_key_env": "OPENAI_API_KEY",
        "api_base": None,
        "cost_per_token": 0.000002,
    },
    "anthropic": {
        "model_prefix": "anthropic/",
        "api_key_env": "ANTHROPIC_API_KEY",
        "api_base": None,
        "cost_per_token": 0.000003,
    },
}


def _classify_error(exc: Exception) -> str:
    """
    Classify a LiteLLM exception into one of:
    rate_limit, auth, quota_exceeded, transient
    """
    exc_str = str(exc).lower()
    if isinstance(exc, RateLimitError) or "429" in exc_str or "rate limit" in exc_str:
        return "rate_limit"
    if isinstance(exc, AuthenticationError) or "401" in exc_str or "authentication" in exc_str:
        return "auth"
    if "402" in exc_str or "quota" in exc_str or "billing" in exc_str or "insufficient" in exc_str:
        return "quota_exceeded"
    return "transient"


class LiteLLMProvider(ProviderBase):
    """
    Provider implementation backed by LiteLLM.
    Supports all 8 cloud providers with streaming and error classification.
    """

    def __init__(
        self,
        provider_id: str,
        model_id: str,
        encrypted_api_key: str,
        session_id: str = "system",
    ) -> None:
        super().__init__(provider_id, model_id)
        self._encrypted_api_key = encrypted_api_key
        self._session_id = session_id
        config = _PROVIDER_CONFIG.get(provider_id, {})
        self._api_base: str | None = config.get("api_base")
        self._cost_per_token: float = config.get("cost_per_token", 0.0)

    def _get_api_key(self) -> str:
        """Decrypt and return the API key."""
        return decrypt_api_key(self._encrypted_api_key)

    def get_metrics(self) -> dict:
        metrics = super().get_metrics()
        metrics["cost_per_token"] = self._cost_per_token
        return metrics

    async def complete(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Send messages to the provider via LiteLLM.
        Returns full string if stream=False, async generator if stream=True.
        """
        if stream:
            return self._stream_complete(messages)
        return await self._full_complete(messages)

    async def _full_complete(self, messages: list[dict]) -> str:
        """Non-streaming completion."""
        start = time.perf_counter()
        api_key = self._get_api_key()

        kwargs: dict = {
            "model": self.model_id,
            "messages": messages,
            "api_key": api_key,
            "stream": False,
        }
        if self._api_base:
            kwargs["api_base"] = self._api_base

        try:
            response = await litellm.acompletion(**kwargs)
            latency_ms = (time.perf_counter() - start) * 1000
            tokens = response.usage.total_tokens if response.usage else 0
            content = response.choices[0].message.content or ""

            self._record_success(tokens, latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status="success",
            ).inc()
            provider_latency_seconds.labels(provider_id=self.provider_id).observe(
                latency_ms / 1000
            )
            token_usage_total.labels(
                provider_id=self.provider_id,
                session_id=self._session_id,
            ).inc(tokens)

            logger.debug(
                "provider_completion",
                provider_id=self.provider_id,
                tokens=tokens,
                latency_ms=round(latency_ms, 2),
            )
            return content

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            error_type = _classify_error(exc)
            self._record_error(latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status=error_type,
            ).inc()

            logger.error(
                "provider_completion_error",
                provider_id=self.provider_id,
                error_type=error_type,
                error=str(exc),
            )

            # Apply cooldown based on error type
            if error_type == "rate_limit":
                self.set_cooldown(60.0)
            elif error_type == "quota_exceeded":
                self.set_cooldown(3600.0)
            elif error_type == "auth":
                self.set_cooldown(300.0)

            raise

    async def _stream_complete(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Streaming completion — yields string chunks as they arrive."""
        start = time.perf_counter()
        api_key = self._get_api_key()

        kwargs: dict = {
            "model": self.model_id,
            "messages": messages,
            "api_key": api_key,
            "stream": True,
        }
        if self._api_base:
            kwargs["api_base"] = self._api_base

        total_tokens = 0
        try:
            response = await litellm.acompletion(**kwargs)
            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    total_tokens += 1  # approximate
                    yield delta

            latency_ms = (time.perf_counter() - start) * 1000
            self._record_success(total_tokens, latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status="success",
            ).inc()
            provider_latency_seconds.labels(provider_id=self.provider_id).observe(
                latency_ms / 1000
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            error_type = _classify_error(exc)
            self._record_error(latency_ms)
            provider_requests_total.labels(
                provider_id=self.provider_id,
                model_id=self.model_id,
                status=error_type,
            ).inc()
            logger.error(
                "provider_stream_error",
                provider_id=self.provider_id,
                error_type=error_type,
                error=str(exc),
            )
            if error_type == "rate_limit":
                self.set_cooldown(60.0)
            elif error_type == "quota_exceeded":
                self.set_cooldown(3600.0)
            raise

    async def health_check(self) -> bool:
        """Ping the provider with a minimal request to verify availability."""
        try:
            api_key = self._get_api_key()
            kwargs: dict = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": "ping"}],
                "api_key": api_key,
                "max_tokens": 1,
                "stream": False,
            }
            if self._api_base:
                kwargs["api_base"] = self._api_base
            await litellm.acompletion(**kwargs)
            return True
        except Exception as exc:
            logger.warning(
                "provider_health_check_failed",
                provider_id=self.provider_id,
                error=str(exc),
            )
            return False
