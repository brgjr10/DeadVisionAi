"""
Provider registry with hot-swap support.
Providers can be registered and deregistered at runtime without restart.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from app.observability.logging_config import get_logger
from app.providers.base import ProviderBase

logger = get_logger(__name__)


class ProviderRegistry:
    """
    Thread-safe registry for AI providers.
    Supports hot-registration and graceful deregistration.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderBase] = {}
        self._in_flight: dict[str, int] = {}  # provider_id -> active request count
        self._lock = asyncio.Lock()

    async def register(self, provider: ProviderBase) -> None:
        """
        Register a provider. If a provider with the same ID already exists,
        it is replaced after in-flight requests complete.
        """
        async with self._lock:
            if provider.provider_id in self._providers:
                logger.info(
                    "provider_hot_swap",
                    provider_id=provider.provider_id,
                    in_flight=self._in_flight.get(provider.provider_id, 0),
                )
                # Wait for in-flight requests to drain
                while self._in_flight.get(provider.provider_id, 0) > 0:
                    await asyncio.sleep(0.1)

            self._providers[provider.provider_id] = provider
            self._in_flight[provider.provider_id] = 0
            logger.info("provider_registered", provider_id=provider.provider_id)

    def register_sync(self, provider: ProviderBase) -> None:
        """
        Synchronous registration for use during startup (no in-flight drain).
        """
        self._providers[provider.provider_id] = provider
        self._in_flight[provider.provider_id] = 0
        logger.info("provider_registered_sync", provider_id=provider.provider_id)

    async def deregister(self, provider_id: str) -> None:
        """
        Deregister a provider. Waits for in-flight requests to complete first.
        """
        async with self._lock:
            if provider_id not in self._providers:
                logger.warning("provider_not_found_for_deregister", provider_id=provider_id)
                return

            # Drain in-flight requests
            while self._in_flight.get(provider_id, 0) > 0:
                logger.debug(
                    "waiting_for_in_flight",
                    provider_id=provider_id,
                    count=self._in_flight[provider_id],
                )
                await asyncio.sleep(0.1)

            del self._providers[provider_id]
            self._in_flight.pop(provider_id, None)
            logger.info("provider_deregistered", provider_id=provider_id)

    def get_available(self) -> list[ProviderBase]:
        """Return all providers that are currently available (not in cooldown)."""
        return [p for p in self._providers.values() if p.is_available]

    def get_by_id(self, provider_id: str) -> Optional[ProviderBase]:
        """Return a provider by ID, or None if not found."""
        return self._providers.get(provider_id)

    def list_all(self) -> list[dict]:
        """Return a list of all provider status dicts for the API response."""
        return [
            {
                "provider_id": p.provider_id,
                "model_id": p.model_id,
                "is_available": p.is_available,
                "is_in_cooldown": p.is_in_cooldown,
                "quota_remaining_pct": p.quota_remaining_pct,
                **p.get_metrics(),
            }
            for p in self._providers.values()
        ]

    def increment_in_flight(self, provider_id: str) -> None:
        """Increment the in-flight request counter for a provider."""
        self._in_flight[provider_id] = self._in_flight.get(provider_id, 0) + 1

    def decrement_in_flight(self, provider_id: str) -> None:
        """Decrement the in-flight request counter for a provider."""
        current = self._in_flight.get(provider_id, 0)
        self._in_flight[provider_id] = max(0, current - 1)

    def __len__(self) -> int:
        return len(self._providers)


_registry_instance: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Return the singleton ProviderRegistry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ProviderRegistry()
    return _registry_instance
