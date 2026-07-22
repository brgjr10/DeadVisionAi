"""
Abstract base class for all AI providers.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Union

from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class ProviderBase(ABC):
    """
    Abstract interface that all provider implementations must satisfy.
    Handles cooldown management and basic metrics tracking.
    """

    def __init__(self, provider_id: str, model_id: str) -> None:
        self.provider_id = provider_id
        self.model_id = model_id
        self._cooldown_until: float = 0.0
        self._request_count: int = 0
        self._token_count: int = 0
        self._error_count: int = 0
        self._total_latency_ms: float = 0.0
        self._last_failure: float = 0.0
        self._quota_remaining_pct: float = 1.0

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Send messages to the model and return the completion.
        If stream=True, returns an async generator yielding string chunks.
        If stream=False, returns the full completion string.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a lightweight health check against the provider.
        Returns True if the provider is reachable and functional.
        """
        ...

    def get_metrics(self) -> dict:
        """Return current provider metrics as a dict."""
        avg_latency = (
            self._total_latency_ms / self._request_count
            if self._request_count > 0
            else 0.0
        )
        error_rate = (
            self._error_count / self._request_count
            if self._request_count > 0
            else 0.0
        )
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "request_count": self._request_count,
            "token_count": self._token_count,
            "error_count": self._error_count,
            "avg_latency_ms": round(avg_latency, 2),
            "latency_ms": round(avg_latency, 2),
            "error_rate": round(error_rate, 4),
            "last_failure": self._last_failure,
            "quota_remaining_pct": self._quota_remaining_pct,
            "in_cooldown": self.is_in_cooldown,
            "cost_per_token": 0.0,  # overridden by subclasses
        }

    @property
    def is_available(self) -> bool:
        """True if the provider is not in cooldown."""
        return not self.is_in_cooldown

    @property
    def is_in_cooldown(self) -> bool:
        """True if the provider is currently in cooldown."""
        return time.time() < self._cooldown_until

    @property
    def quota_remaining_pct(self) -> float:
        """Remaining quota as a fraction (0.0-1.0)."""
        return self._quota_remaining_pct

    def set_cooldown(self, duration_seconds: float) -> None:
        """Put this provider into cooldown for the given duration."""
        self._cooldown_until = time.time() + duration_seconds
        self._last_failure = time.time()
        logger.warning(
            "provider_cooldown",
            provider_id=self.provider_id,
            duration_seconds=duration_seconds,
        )

    def clear_cooldown(self) -> None:
        """Clear the cooldown, making the provider available immediately."""
        self._cooldown_until = 0.0
        logger.info("provider_cooldown_cleared", provider_id=self.provider_id)

    def _record_success(self, tokens: int, latency_ms: float) -> None:
        """Record a successful request."""
        self._request_count += 1
        self._token_count += tokens
        self._total_latency_ms += latency_ms

    def _record_error(self, latency_ms: float = 0.0) -> None:
        """Record a failed request."""
        self._request_count += 1
        self._error_count += 1
        self._last_failure = time.time()
        if latency_ms > 0:
            self._total_latency_ms += latency_ms
