"""
Data models for task classification and routing decisions.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class TaskClassification(BaseModel):
    """Output of the TaskClassifier for a given task."""

    intent: str = Field(
        ...,
        description="Classified intent category",
    )
    complexity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Complexity score from 0.0 (trivial) to 1.0 (very complex)",
    )
    estimated_tokens: int = Field(
        default=0,
        ge=0,
        description="Estimated token count for the task",
    )
    recommended_tools: list[str] = Field(
        default_factory=list,
        description="List of recommended MCP tool IDs",
    )
    tool_only_flag: bool = Field(
        default=False,
        description="True if task can be handled by tools without LLM involvement",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Classifier confidence in this classification",
    )


class RoutingDecision(BaseModel):
    """Output of the MasterRouter for a given task."""

    provider_id: str = Field(..., description="Selected provider identifier")
    model_id: str = Field(..., description="Selected model identifier")
    estimated_cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated cost in USD for this request",
    )
    routing_reason: str = Field(
        default="",
        description="Human-readable explanation of the routing decision",
    )
    fallback_chain: list[str] = Field(
        default_factory=list,
        description="Ordered list of fallback provider IDs",
    )
    is_local: bool = Field(
        default=False,
        description="True if routed to a local model",
    )


class ProviderScore(BaseModel):
    """Computed routing score for a single provider."""

    provider_id: str
    score: float = Field(ge=0.0, le=1.0)
    latency_ms: float = Field(default=0.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    quota_remaining: float = Field(default=1.0, ge=0.0, le=1.0)
    in_cooldown: bool = Field(default=False)
