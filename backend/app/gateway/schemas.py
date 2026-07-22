"""
Pydantic request/response models for the API Gateway.
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """Incoming task submission from a client."""

    session_id: str = Field(..., description="Session identifier")
    content: str = Field(..., min_length=1, description="Task content / user message")
    task_type: Optional[str] = Field(
        default=None,
        description="Optional hint for task type (overrides classifier)",
    )
    stream: bool = Field(default=True, description="Whether to stream the response")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional client-supplied metadata",
    )


class TaskResponse(BaseModel):
    """Completed task response returned to the client."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    content: str
    model_used: str
    provider: str
    tokens_used: int = Field(default=0)
    cached: bool = Field(default=False)
    tool_used: Optional[str] = Field(default=None)
    duration_ms: Optional[float] = Field(default=None)


class StreamChunk(BaseModel):
    """A single streaming token chunk sent over WebSocket."""

    request_id: str
    delta: str
    done: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobQueued(BaseModel):
    """Response when a task is queued for deferred processing."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    estimated_wait: Optional[float] = Field(
        default=None,
        description="Estimated wait time in seconds",
    )
    message: str = Field(default="Task queued for processing")


class JobStatus(BaseModel):
    """Status of a queued job."""

    job_id: str
    session_id: str
    status: str  # "queued" | "processing" | "completed" | "failed"
    result: Optional[TaskResponse] = None
    error: Optional[str] = None


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""

    user_id: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionCreateResponse(BaseModel):
    """Response containing the new session token."""

    session_id: str
    token: str
    expires_in: int = Field(description="Token TTL in seconds")


class ErrorResponse(BaseModel):
    """Structured error response."""

    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    uptime_seconds: float
