"""
Master routing engine.
Selects the optimal provider/model for each task using local-first strategy.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.gateway.schemas import TaskRequest
from app.observability.logging_config import get_logger
from app.routing.classifier import TaskClassification
from app.routing.schemas import RoutingDecision
from app.routing.scoring import ProviderScorer

logger = get_logger(__name__)

# Local provider ID used for llama.cpp server
_LOCAL_PROVIDER_ID = "llamacpp"
_LOCAL_MODEL_ID = "local-model"

# Free-tier cloud fallback order (cheapest / zero-cost first)
# Paid-only providers (openai, anthropic, together, fireworks) are intentionally
# excluded; add them here only if FREE_TIER_STRICT=false in the environment.
_CLOUD_FALLBACK_ORDER = [
    "groq",
    "deepseek",
    "openrouter",
    "gemini",
    "searxng",
    "ollama",
]

# Default models per free-tier provider
_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.1-8b-instant",
    "deepseek": "deepseek-chat",
    "openrouter": "openai/gpt-4o-mini",
    "gemini": "gemini-2.0-flash-lite",
    "searxng": "searxng/search",
    "ollama": _LOCAL_MODEL_ID,
}


class RoutingError(Exception):
    """Raised when all providers fail after max retries."""

    def __init__(self, message: str, attempted_providers: list[str], reasons: list[str]) -> None:
        super().__init__(message)
        self.attempted_providers = attempted_providers
        self.reasons = reasons


class MasterRouter:
    """
    Routes tasks to the optimal provider using local-first strategy.

    Strategy:
    1. If complexity < LOCAL_COMPLEXITY_THRESHOLD → try local model
    2. If local confidence < CONFIDENCE_THRESHOLD → escalate to cloud
    3. If complexity >= ESCALATION_THRESHOLD → go directly to cloud
    4. Select cloud provider by highest weighted score
    5. On rate-limit → cooldown + retry next provider
    6. After 3 consecutive failures → return structured error
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._scorer = ProviderScorer()
        self._health_registry: dict[str, dict] = {}
        self._health_last_updated: float = 0.0
        self._health_task: Optional[asyncio.Task] = None
        self._cooldown_providers: dict[str, float] = {}  # provider_id -> expiry timestamp

    def start_health_monitor(self) -> None:
        """Start the background health registry refresh task."""
        if self._health_task is None or self._health_task.done():
            self._health_task = asyncio.create_task(self._health_refresh_loop())
            logger.info("health_monitor_started")

    def stop_health_monitor(self) -> None:
        """Stop the background health refresh task."""
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            logger.info("health_monitor_stopped")

    async def _health_refresh_loop(self) -> None:
        """Periodically refresh the provider health registry."""
        while True:
            try:
                await self._refresh_health_registry()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("health_refresh_error", error=str(exc))
            await asyncio.sleep(self._settings.provider_health_interval)

    async def _refresh_health_registry(self) -> None:
        """Update health metrics for all registered providers."""
        try:
            from app.providers.registry import get_provider_registry

            registry = get_provider_registry()
            providers = registry.get_available()

            for provider in providers:
                try:
                    metrics = provider.get_metrics()
                    self._health_registry[provider.provider_id] = metrics
                except Exception as exc:
                    logger.warning(
                        "provider_health_check_failed",
                        provider_id=provider.provider_id,
                        error=str(exc),
                    )
                    self._health_registry[provider.provider_id] = {
                        "in_cooldown": True,
                        "quota_remaining_pct": 0.0,
                        "latency_ms": 9999.0,
                        "error_rate": 1.0,
                        "cost_per_token": 0.0,
                    }

            self._health_last_updated = time.time()
            logger.debug("health_registry_refreshed", provider_count=len(providers))
        except Exception as exc:
            logger.error("health_registry_refresh_failed", error=str(exc))

    def _is_health_stale(self) -> bool:
        """Return True if the health registry hasn't been updated within the interval."""
        if self._health_last_updated == 0.0:
            return False  # Never updated yet — allow initial routing
        age = time.time() - self._health_last_updated
        return age > self._settings.provider_health_interval

    def _set_cooldown(self, provider_id: str, duration_seconds: float = 60.0) -> None:
        """Put a provider into cooldown for the given duration."""
        self._cooldown_providers[provider_id] = time.time() + duration_seconds
        logger.warning("provider_cooldown_set", provider_id=provider_id, duration=duration_seconds)

    def _is_in_cooldown(self, provider_id: str) -> bool:
        """Return True if the provider is currently in cooldown."""
        expiry = self._cooldown_providers.get(provider_id, 0.0)
        if time.time() < expiry:
            return True
        # Cooldown expired — clean up
        self._cooldown_providers.pop(provider_id, None)
        return False

    def _get_cloud_provider_order(self) -> list[str]:
        """Return cloud providers ranked by current score, excluding cooldown providers."""
        if self._is_health_stale():
            logger.warning("health_registry_stale_suspending_routing")
            return []

        metrics_map = {
            pid: metrics
            for pid, metrics in self._health_registry.items()
            if pid != _LOCAL_PROVIDER_ID and not self._is_in_cooldown(pid)
        }

        if not metrics_map:
            # Fall back to static order if no health data
            return [p for p in _CLOUD_FALLBACK_ORDER if not self._is_in_cooldown(p)]

        return self._scorer.rank_providers(metrics_map)

    async def _try_local(self, task: TaskRequest) -> Optional[RoutingDecision]:
        """Attempt to route to the local Ollama model."""
        try:
            from app.providers.registry import get_provider_registry

            registry = get_provider_registry()
            local = registry.get_by_id(_LOCAL_PROVIDER_ID)
            if local is None or not local.is_available:
                return None

            return RoutingDecision(
                provider_id=_LOCAL_PROVIDER_ID,
                model_id=_LOCAL_MODEL_ID,
                estimated_cost=0.0,
                routing_reason="local-first: complexity below threshold",
                fallback_chain=self._get_cloud_provider_order()[:3],
                is_local=True,
            )
        except Exception as exc:
            logger.warning("local_routing_check_failed", error=str(exc))
            return None

    async def route(
        self,
        task: TaskRequest,
        classification: TaskClassification,
    ) -> RoutingDecision:
        """
        Select the optimal provider for the given task.
        Implements local-first strategy with cloud escalation.
        Raises RoutingError after max retries.
        """
        settings = self._settings
        attempted: list[str] = []
        reasons: list[str] = []

        # 1. Local-first: try local model for simple tasks
        if classification.complexity_score < settings.local_complexity_threshold:
            local_decision = await self._try_local(task)
            if local_decision is not None:
                logger.info(
                    "routed_to_local",
                    complexity=classification.complexity_score,
                    threshold=settings.local_complexity_threshold,
                )
                return local_decision
            logger.info("local_model_unavailable_escalating_to_cloud")

        # 2. Cloud routing
        cloud_order = self._get_cloud_provider_order()

        if not cloud_order:
            # No health data yet — use static fallback order
            cloud_order = [p for p in _CLOUD_FALLBACK_ORDER if not self._is_in_cooldown(p)]

        if not cloud_order:
            raise RoutingError(
                "All providers are in cooldown",
                attempted_providers=attempted,
                reasons=reasons,
            )

        for provider_id in cloud_order[: settings.max_retries]:
            if self._is_in_cooldown(provider_id):
                continue

            try:
                from app.providers.registry import get_provider_registry

                registry = get_provider_registry()
                provider = registry.get_by_id(provider_id)

                if provider is None or not provider.is_available:
                    attempted.append(provider_id)
                    reasons.append(f"{provider_id}: not available")
                    continue

                model_id = _PROVIDER_DEFAULT_MODELS.get(provider_id, provider_id)
                fallback = [p for p in cloud_order if p != provider_id][:3]

                logger.info(
                    "routed_to_cloud",
                    provider_id=provider_id,
                    model_id=model_id,
                    complexity=classification.complexity_score,
                )

                return RoutingDecision(
                    provider_id=provider_id,
                    model_id=model_id,
                    estimated_cost=0.0,
                    routing_reason=f"cloud: complexity={classification.complexity_score:.2f}",
                    fallback_chain=fallback,
                    is_local=False,
                )

            except Exception as exc:
                attempted.append(provider_id)
                reasons.append(f"{provider_id}: {exc}")
                logger.warning("provider_routing_failed", provider_id=provider_id, error=str(exc))

        raise RoutingError(
            f"All {len(attempted)} providers failed",
            attempted_providers=attempted,
            reasons=reasons,
        )

    def handle_provider_error(self, provider_id: str, error_type: str) -> None:
        """
        Handle a provider error by setting cooldown if rate-limited.
        Called by the provider layer after an error response.
        """
        if error_type == "rate_limit":
            self._set_cooldown(provider_id, duration_seconds=60.0)
        elif error_type == "quota_exceeded":
            self._set_cooldown(provider_id, duration_seconds=3600.0)
        elif error_type == "auth":
            self._set_cooldown(provider_id, duration_seconds=300.0)
        else:
            # Transient error — short cooldown
            self._set_cooldown(provider_id, duration_seconds=30.0)


_master_router_instance: Optional[MasterRouter] = None


def get_master_router() -> MasterRouter:
    """Return the singleton MasterRouter instance."""
    global _master_router_instance
    if _master_router_instance is None:
        _master_router_instance = MasterRouter()
    return _master_router_instance
