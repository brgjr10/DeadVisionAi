"""
Provider weighted scoring system.
Computes a routing score for each provider based on multiple factors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.observability.logging_config import get_logger
from app.routing.schemas import ProviderScore

logger = get_logger(__name__)


@dataclass
class ScoringWeights:
    """Configurable weights for the provider scoring formula."""

    quota: float = 0.35
    latency: float = 0.25
    error: float = 0.25
    cost: float = 0.15

    def __post_init__(self) -> None:
        total = self.quota + self.latency + self.error + self.cost
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")


class ProviderScorer:
    """
    Computes weighted routing scores for providers.

    Score formula:
        score = (quota_weight * quota_remaining_pct)
              + (latency_weight * latency_score)
              + (error_weight * (1 - error_rate))
              + (cost_weight * cost_score)

    Returns 0.0 if provider is in cooldown or quota is exhausted.
    """

    def __init__(self, weights: Optional[ScoringWeights] = None) -> None:
        self.weights = weights or ScoringWeights()

    def _latency_score(self, latency_ms: float) -> float:
        """
        Convert latency in ms to a 0.0-1.0 score.
        0ms → 1.0, 5000ms → 0.0 (linear decay).
        """
        if latency_ms <= 0:
            return 1.0
        return max(0.0, 1.0 - (latency_ms / 5000.0))

    def _cost_score(self, cost_per_token: float) -> float:
        """
        Convert cost per token to a 0.0-1.0 score.
        Free (0.0) → 1.0, expensive (0.01/token) → 0.0.
        """
        if cost_per_token <= 0:
            return 1.0
        return max(0.0, 1.0 - (cost_per_token / 0.01))

    def compute_score(self, provider_metrics: dict) -> float:
        """
        Compute a routing score for a provider given its current metrics.

        Expected keys in provider_metrics:
            - in_cooldown: bool
            - quota_remaining_pct: float (0.0-1.0)
            - latency_ms: float
            - error_rate: float (0.0-1.0)
            - cost_per_token: float (USD per token, 0.0 for free)
        """
        if provider_metrics.get("in_cooldown", False):
            return 0.0

        quota_pct = float(provider_metrics.get("quota_remaining_pct", 1.0))
        if quota_pct <= 0.0:
            return 0.0

        latency_ms = float(provider_metrics.get("latency_ms", 500.0))
        error_rate = float(provider_metrics.get("error_rate", 0.0))
        cost_per_token = float(provider_metrics.get("cost_per_token", 0.0))

        w = self.weights
        score = (
            w.quota * quota_pct
            + w.latency * self._latency_score(latency_ms)
            + w.error * (1.0 - min(error_rate, 1.0))
            + w.cost * self._cost_score(cost_per_token)
        )

        return round(min(max(score, 0.0), 1.0), 4)

    def score_provider(
        self,
        provider_id: str,
        provider_metrics: dict,
    ) -> ProviderScore:
        """Compute and return a ProviderScore for the given provider."""
        score = self.compute_score(provider_metrics)
        return ProviderScore(
            provider_id=provider_id,
            score=score,
            latency_ms=provider_metrics.get("latency_ms", 0.0),
            error_rate=provider_metrics.get("error_rate", 0.0),
            quota_remaining=provider_metrics.get("quota_remaining_pct", 1.0),
            in_cooldown=provider_metrics.get("in_cooldown", False),
        )

    def rank_providers(self, metrics_by_provider: dict[str, dict]) -> list[str]:
        """
        Return provider IDs sorted by descending score.
        Providers with score 0.0 are excluded.
        """
        scored = [
            (pid, self.compute_score(metrics))
            for pid, metrics in metrics_by_provider.items()
        ]
        ranked = sorted(
            [(pid, s) for pid, s in scored if s > 0.0],
            key=lambda x: x[1],
            reverse=True,
        )
        logger.debug("providers_ranked", ranking=[(p, round(s, 3)) for p, s in ranked])
        return [pid for pid, _ in ranked]
