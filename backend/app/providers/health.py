"""
Provider health monitor.
Background task that periodically pings all providers and updates the health registry.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from app.config import get_settings
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class ProviderHealthMonitor:
    """
    Runs a background asyncio task that pings each provider at a configured interval.
    Updates the health registry and marks providers unhealthy on failure.
    Suspends routing if a health update cycle is missed beyond the interval.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._health_registry: dict[str, bool] = {}
        self._last_update: float = 0.0
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def start(self) -> None:
        """Start the background health monitoring task."""
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("health_monitor_started")

    def stop(self) -> None:
        """Stop the background health monitoring task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("health_monitor_stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._run_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("health_monitor_loop_error", error=str(exc))
            await asyncio.sleep(self._settings.provider_health_interval)

    async def _run_health_checks(self) -> None:
        """Ping all registered providers and update health registry."""
        from app.providers.registry import get_provider_registry

        registry = get_provider_registry()
        providers = list(registry._providers.values())

        if not providers:
            self._last_update = time.time()
            return

        tasks = {p.provider_id: asyncio.create_task(p.health_check()) for p in providers}

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for provider_id, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                self._health_registry[provider_id] = False
                logger.warning(
                    "provider_health_check_failed",
                    provider_id=provider_id,
                    error=str(result),
                )
            else:
                self._health_registry[provider_id] = bool(result)
                if not result:
                    logger.warning("provider_unhealthy", provider_id=provider_id)

        self._last_update = time.time()
        healthy_count = sum(1 for v in self._health_registry.values() if v)
        logger.info(
            "health_check_complete",
            total=len(providers),
            healthy=healthy_count,
        )

    def is_provider_healthy(self, provider_id: str) -> bool:
        """Return True if the provider passed its last health check."""
        return self._health_registry.get(provider_id, True)  # assume healthy if unknown

    def is_update_overdue(self) -> bool:
        """Return True if the last health update was missed beyond the interval."""
        if self._last_update == 0.0:
            return False
        age = time.time() - self._last_update
        return age > self._settings.provider_health_interval

    def get_registry(self) -> dict[str, bool]:
        """Return a copy of the current health registry."""
        return dict(self._health_registry)


_monitor_instance: Optional[ProviderHealthMonitor] = None


def get_health_monitor() -> ProviderHealthMonitor:
    """Return the singleton ProviderHealthMonitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = ProviderHealthMonitor()
    return _monitor_instance
