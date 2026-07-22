"""
API Gateway router — REST endpoints and WebSocket handler.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.config import get_settings
from app.gateway.auth import create_session_token, get_current_session
from app.gateway.schemas import (
    ErrorResponse,
    HealthResponse,
    JobQueued,
    JobStatus,
    SessionCreateRequest,
    SessionCreateResponse,
    StreamChunk,
    TaskRequest,
    TaskResponse,
)
from app.memory.manager import get_memory_manager
from app.observability.logging_config import get_logger
from app.observability.metrics import active_sessions

logger = get_logger(__name__)

router = APIRouter()

# In-memory job store (replace with Redis/DB in production)
_job_store: dict[str, dict[str, Any]] = {}
_app_start_time = time.time()

# Episodic context included in the model prompt so it has recall
_EPISODIC_CONTEXT_PREFIX = "Previous conversation context (for reference):\n"
_EPISODIC_CONTEXT_SUFFIX = "\nEnd of previous context.\n\n"


# ─────────────────────────────────────────────
# Session endpoints
# ─────────────────────────────────────────────


@router.post("/api/v1/sessions", response_model=SessionCreateResponse, status_code=201)
async def create_session(body: SessionCreateRequest) -> SessionCreateResponse:
    """Create a new session and return a signed JWT."""
    session_id = str(uuid4())
    token = create_session_token(session_id, user_id=body.user_id)
    logger.info("session_created", session_id=session_id)
    active_sessions.inc()
    return SessionCreateResponse(
        session_id=session_id,
        token=token,
        expires_in=86400,  # 24 hours
        )


# ─────────────────────────────────────────────
# Additional endpoints for frontend integration
# ─────────────────────────────────────────────

# Chat health check endpoint (used by frontend status monitoring)
@router.get("/chat")
async def chat_endpoint_health():
    """Chat service health check."""
    return {"status": "ok", "service": "chat"}

@router.post("/chat")
async def chat_endpoint(request: dict):
    """Chat endpoint for frontend interaction.
    Preserves context across turns by reading/writing episodic memory for
    the given ``session_id``.  When the frontend does not supply one a fresh
    UUID is generated and returned to the client for subsequent calls.
    """

    # ── System prompt injected when tool results are available ─────────────
    # Tells the LLM to ground answers in that external evidence rather than
    # relying on pre-training knowledge for real-time/recency-sensitive queries.
    _TIME_SENSITIVE_TASK_SYSTEM_PROMPT = (
        "The user asked a real-time or recency-sensitive question. "
        "You have already been provided grounded external evidence via tool results above. "
        "Answer ONLY using the provided evidence. "
        "If the evidence contains the answer, state it clearly and cite the source. "
        "If the evidence does not contain the answer, say so honestly — do not guess "
        "or fall back to pre-training knowledge."
    )

    try:
        message = request.get("message", "")
        session_id: str = request.get("session_id") or str(uuid4())
        tools_available = request.get("tools_available", [])

        # Import here to avoid circular imports
        from app.routing.master_router import get_master_router
        from app.routing.classifier import get_task_classifier
        from app.providers.registry import get_provider_registry
        from app.tools.registry import get_tool_registry

        # ── 1. Load episodic memory context ──────────────────────────────────
        memory_manager = get_memory_manager()
        episodic_context_str = ""
        try:
            prev_turns = await memory_manager.get_episodic(session_id, limit=20)
            if prev_turns:
                context_lines = []
                for turn in prev_turns:
                    role = turn.get("role", "unknown")
                    content = turn.get("content", "")
                    if role == "user":
                        context_lines.append(f"User: {content}")
                    elif role == "system":
                        context_lines.append(f"[System note]: {content}")
                    else:
                        context_lines.append(f"Assistant: {content}")
                if context_lines:
                    episodic_context_str = (
                        _EPISODIC_CONTEXT_PREFIX
                        + "\n".join(context_lines)
                        + _EPISODIC_CONTEXT_SUFFIX
                    )
                    logger.info(
                        "episodic_context_loaded",
                        session_id=session_id,
                        turns=len(prev_turns),
                    )
        except Exception as exc:
            logger.warning("episodic_context_load_failed", session_id=session_id, error=str(exc))

        # ── 2. Classify, now seeded with prior turns ─────────────────────────
        classifier = get_task_classifier()
        classification = await classifier.classify(message, context=prev_turns)
        logger.info(
            "router_classification_received",
            intent=classification.intent,
            complexity=classification.complexity_score,
            recommended_tools=classification.recommended_tools,
            tool_only=classification.tool_only_flag,
            confidence=classification.confidence,
        )

        # Prepend episodic context to the message so the LLM can recall prior
        # turns before it starts answering.
        context_seeded_message = f"{episodic_context_str}{message}" if episodic_context_str else message

        # ── 3. Execute recommended tools ─────────────────────────────────────
        tool_results = {}
        print(f"  *** CLASSIFIER *** intent={classification.intent!r} rec_tools={classification.recommended_tools!r}")
        if classification.recommended_tools:
            tool_registry = get_tool_registry()
            for tool_id in classification.recommended_tools:
                in_registry = tool_id in tool_registry._tools
                if in_registry:
                    # Pass the context-seeded message so web_search can leverage
                    # prior-turn context for better results when relevant.
                    params: dict[str, Any] = {"query": context_seeded_message}
                    if tool_id == "web_search":
                        params["max_results"] = 3

                    result = await tool_registry.execute_tool(tool_id, params)
                    logger.info(
                        "router_tool_exec_done",
                        tool_id=tool_id,
                        success=result.success,
                        error=str(result.error) if result.error else None,
                    )
                    if result.success:
                        tool_results[tool_id] = result.result

        logger.info(
            "router_before_fallback",
            intent=classification.intent,
            recommended_tools=classification.recommended_tools,
            tool_results_keys=list(tool_results.keys()),
        )

        print(f"  *** BEFORE_FALLBACK *** tool_results={list(tool_results.keys())!r} intent={classification.intent!r}")
        # Router-level fallback: if classifier tagged intent=web-search but
        # recommended_tools came back empty, force web_search ourselves.
        if not tool_results and classification.intent == "web-search":
            tool_registry = get_tool_registry()
            print(f"  *** FALLBACK TRIGGERED *** intent={classification.intent!r} rec_tools={classification.recommended_tools!r} registry={list(tool_registry._tools.keys())}")
            if "web_search" in tool_registry._tools:
                result = await tool_registry.execute_tool(
                    "web_search", {"query": context_seeded_message, "max_results": 3}
                )
                logger.info(
                    "router_tool_fallback_web_search",
                    success=result.success,
                )
                if result.success:
                    tool_results["web_search"] = result.result
                    print(f"  *** FALLBACK RESULT *** success=True")
                else:
                    print(f"  *** FALLBACK RESULT *** success=False error={str(result.error)[:100]!r}")

        print(f"  *** TOOL_RESULTS_KEYS *** {list(tool_results.keys())}")

        # ── 4. Build the enhanced prompt ─────────────────────────────────────
        enhanced_message = context_seeded_message
        if tool_results:
            tool_context = "\n\nAvailable tool results:\n"
            for tool_id, result in tool_results.items():
                tool_context += f"- {tool_id}: {json.dumps(result)[:500]}\n"
            enhanced_message = enhanced_message + tool_context

        master_router = get_master_router()
        decision = await master_router.route(
            type('TaskRequest', (), {
                'content': enhanced_message,
                'stream': False
            })(),
            classification
        )

        registry = get_provider_registry()
        provider = registry.get_by_id(decision.provider_id)

        if provider is None:
            return JSONResponse(
                status_code=503,
                content={"error": f"Provider '{decision.provider_id}' is not available"}
            )

        if tool_results:
            messages = [
                {"role": "system", "content": _TIME_SENSITIVE_TASK_SYSTEM_PROMPT},
                {"role": "user", "content": enhanced_message},
            ]
        else:
            messages = [{"role": "user", "content": enhanced_message}]
        result = await provider.complete(messages, stream=False)

        # ── 5. Persist this turn to episodic memory ───────────────────────────
        try:
            await memory_manager.store_episodic(session_id, "user", message)
            await memory_manager.store_episodic(session_id, "assistant", str(result))
            logger.info(
                "episodic_turn_stored",
                session_id=session_id,
            )
        except Exception as exc:
            logger.warning("episodic_turn_store_failed", session_id=session_id, error=str(exc))

        # Prepare tool calls info for response
        tool_calls_info = []
        if tool_results:
            for tool_id, raw in tool_results.items():
                if isinstance(raw, list):
                    raw_pretty = f"{len(raw)} results"
                elif isinstance(raw, dict):
                    raw_pretty = ", ".join(f"{k}={v}" for k, v in list(raw.items())[:3])
                else:
                    raw_pretty = str(raw)[:120]
                tool_calls_info.append({
                    "name": tool_id,
                    "description": f"{tool_id}: {raw_pretty}",
                })

        return JSONResponse(content={
            "response": result,
            "tool_calls": tool_calls_info,
            "model_used": decision.model_id,
            "provider": decision.provider_id,
            "session_id": session_id,
            "classification": {
                "intent": classification.intent,
                "complexity_score": classification.complexity_score,
                "tools_used": list(tool_results.keys())
            }
        })

    except Exception as exc:
        logger.error("chat_endpoint_error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)}
        )


# Tools listing endpoint (used by frontend)
@router.get("/tools")
async def get_available_tools():
    """Get list of available MCP tools for frontend."""
    try:
        from app.tools.registry import get_tool_registry
        registry = get_tool_registry()
        tools = registry.list_tools()
        return {"tools": tools}
    except Exception as exc:
        logger.error("get_tools_error", error=str(exc))
        return {"tools": [], "error": str(exc)}


# ─────────────────────────────────────────────
# Health and observability endpoints
# ─────────────────────────────────────────────


@router.get("/api/v1/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """System health check endpoint."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        uptime_seconds=round(time.time() - _app_start_time, 2),
    )


@router.get("/api/v1/providers")
async def list_providers() -> dict:
    """List all registered providers and their current status."""
    try:
        from app.providers.registry import get_provider_registry

        registry = get_provider_registry()
        return {"providers": registry.list_all()}
    except Exception as exc:
        logger.error("list_providers_error", error=str(exc))
        return {"providers": [], "error": str(exc)}


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Expose Prometheus metrics."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
