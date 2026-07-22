"""
Provider optimization system.
Tracks per-provider metrics and computes weighted routing scores.
"""
from __future__ import annotations

import time
from typing import Optional

from app.observability.logging_config import get_logger
from app.routing.scoring import ProviderScorer, ScoringWeights

logger = get_logger(__name__)

# Warning threshold: reduce weight proportionally above this usage
_WARNING_THRESHOLD_PCT = 0.80  # 80% quota used
# Hard limit: set weight to 0 above this usage
_HARD_LIMIT_PCT = 0.95  # 95% quota used


class ProviderOptimizer:
    """
    Tracks provider performance metrics and computes routing scores.
    Integrates with the MasterRouter for dynamic provider selection.
    """

    def __init__(self, weights: Optional[ScoringWeights] = None) -> None:
        self._scorer = ProviderScorer(weights)
        self._metrics: dict[str, dict] = {}
        self._weight_overrides: dict[str, float] = {}

    def _ensure_provider(self, provider_id: str) -> None:
        """Initialize metrics for a provider if not already tracked."""
        if provider_id not in self._metrics:
            self._metrics[provider_id] = {
                "token_count": 0,
                "request_count": 0,
                "rate_limit_events": 0,
                "failure_count": 0,
                "total_latency_ms": 0.0,
                "cooldown_expiry": 0.0,
                "quota_limit": 1_000_000,  # default quota
                "cost_per_token": 0.0,
            }

    def update_metrics(
        self,
        provider_id: str,
        tokens: int = 0,
        latency_ms: float = 0.0,
        error_type: Optional[str] = None,
    ) -> None:
        """
        Update metrics for a provider after a request completes.
        error_type: None (success), "rate_limit", "auth", "quota_exceeded", "transient"
        """
        self._ensure_provider(provider_id)
        m = self._metrics[provider_id]
        m["request_count"] += 1
        m["token_count"] += tokens
        m["total_latency_ms"] += latency_ms

        if error_type == "rate_limit":
            m["rate_limit_events"] += 1
            m["failure_count"] += 1
        elif error_type in ("auth", "quota_exceeded", "transient"):
            m["failure_count"] += 1

        # Check thresholds
        self.check_warning_threshold(provider_id)
        self.check_hard_limit(provider_id)

        logger.debug(
            "provider_metrics_updated",
            provider_id=provider_id,
            tokens=tokens,
            error_type=error_type,
        )

    def _compute_quota_remaining(self, provider_id: str) -> float:
        """Compute remaining quota as a fraction (0.0-1.0)."""
        m = self._metrics.get(provider_id, {})
        limit = m.get("quota_limit", 1_000_000)
        used = m.get("token_count", 0)
        if limit <= 0:
            return 1.0
        return max(0.0, 1.0 - (used / limit))

    def _compute_error_rate(self, provider_id: str) -> float:
        """Compute error rate as a fraction (0.0-1.0)."""
        m = self._metrics.get(provider_id, {})
        requests = m.get("request_count", 0)
        failures = m.get("failure_count", 0)
        if requests == 0:
            return 0.0
        return min(failures / requests, 1.0)

    def _compute_avg_latency(self, provider_id: str) -> float:
        """Compute average latency in ms."""
        m = self._metrics.get(provider_id, {})
        requests = m.get("request_count", 0)
        total = m.get("total_latency_ms", 0.0)
        if requests == 0:
            return 500.0  # default assumption
        return total / requests

    def compute_all_scores(self) -> dict[str, float]:
        """Compute routing scores for all tracked providers."""
        scores = {}
        for provider_id in self._metrics:
            metrics = self._build_scoring_metrics(provider_id)
            base_score = self._scorer.compute_score(metrics)
            # Apply weight override if set
            override = self._weight_overrides.get(provider_id, 1.0)
            scores[provider_id] = round(base_score * override, 4)
        return scores

    def _build_scoring_metrics(self, provider_id: str) -> dict:
        """Build the metrics dict expected by ProviderScorer."""
        m = self._metrics.get(provider_id, {})
        cooldown_expiry = m.get("cooldown_expiry", 0.0)
        in_cooldown = time.time() < cooldown_expiry

        return {
            "in_cooldown": in_cooldown,
            "quota_remaining_pct": self._compute_quota_remaining(provider_id),
            "latency_ms": self._compute_avg_latency(provider_id),
            "error_rate": self._compute_error_rate(provider_id),
            "cost_per_token": m.get("cost_per_token", 0.0),
        }

    def get_ranked_providers(self, capability_tier: str = "standard") -> list[str]:
        """Return provider IDs sorted by descending score for the given tier."""
        scores = self.compute_all_scores()
        ranked = sorted(
            [(pid, s) for pid, s in scores.items() if s > 0.0],
            key=lambda x: x[1],
            reverse=True,
        )
        return [pid for pid, _ in ranked]

    def check_warning_threshold(self, provider_id: str) -> None:
        """Reduce routing weight proportionally when quota usage exceeds warning threshold."""
        quota_remaining = self._compute_quota_remaining(provider_id)
        quota_used = 1.0 - quota_remaining
        if quota_used >= _WARNING_THRESHOLD_PCT:
            # Reduce weight proportionally: at 80% used → 0.5x, at 95% → 0.0x
            reduction = (quota_used - _WARNING_THRESHOLD_PCT) / (_HARD_LIMIT_PCT - _WARNING_THRESHOLD_PCT)
            override = max(0.0, 1.0 - reduction)
            self._weight_overrides[provider_id] = override
            logger.warning(
                "provider_warning_threshold",
                provider_id=provider_id,
                quota_used_pct=round(quota_used * 100, 1),
                weight_override=round(override, 3),
            )

    def check_hard_limit(self, provider_id: str) -> None:
        """Set routing weight to 0 when quota usage exceeds hard limit."""
        quota_remaining = self._compute_quota_remaining(provider_id)
        if quota_remaining <= (1.0 - _HARD_LIMIT_PCT):
            self._weight_overrides[provider_id] = 0.0
            logger.warning(
                "provider_hard_limit_reached",
                provider_id=provider_id,
            )

    def restore_after_cooldown(self, provider_id: str) -> None:
        """Restore a provider's routing weight to baseline after cooldown expires."""
        self._weight_overrides.pop(provider_id, None)
        if provider_id in self._metrics:
            self._metrics[provider_id]["cooldown_expiry"] = 0.0
        logger.info("provider_weight_restored", provider_id=provider_id)

    def get_all_metrics(self) -> dict[str, dict]:
        """Return all tracked metrics for Prometheus/Observability exposure."""
        result = {}
        for provider_id in self._metrics:
            result[provider_id] = {
                **self._metrics[provider_id],
                "score": self.compute_all_scores().get(provider_id, 0.0),
                "quota_remaining_pct": self._compute_quota_remaining(provider_id),
                "error_rate": self._compute_error_rate(provider_id),
                "avg_latency_ms": self._compute_avg_latency(provider_id),
            }
        return result


_optimizer_instance: Optional[ProviderOptimizer] = None


def get_provider_optimizer() -> ProviderOptimizer:
    """Return the singleton ProviderOptimizer instance."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = ProviderOptimizer()
    return _optimizer_instance
