"""
FastAPI middleware: request logging, CORS, and rate limiting.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.logging_config import bind_request_id, clear_request_context, get_logger
from app.observability.metrics import request_duration_seconds, request_total

logger = get_logger(__name__)

# Simple in-memory rate limiter (per IP, per minute)
# For production, use Redis-backed sliding window
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_REQUESTS = 60  # requests per window
_RATE_LIMIT_WINDOW = 60.0  # seconds


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Adds a unique X-Request-ID header to every request and clears context on response.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        bind_request_id(request_id)
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        finally:
            clear_request_context()

        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with a unique request ID and records Prometheus metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        bind_request_id(request_id)
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(
                "unhandled_request_error",
                method=request.method,
                path=request.url.path,
                error=str(exc),
            )
            raise
        finally:
            duration = time.perf_counter() - start
            status_code = getattr(response, "status_code", 500)

            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                duration_ms=round(duration * 1000, 2),
            )

            request_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status=str(status_code),
            ).inc()
            request_duration_seconds.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(duration)

            clear_request_context()

        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple per-IP rate limiter.
    Returns HTTP 429 with Retry-After header when limit is exceeded.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Slide the window
        timestamps = _rate_limit_store[client_ip]
        _rate_limit_store[client_ip] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]

        if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_REQUESTS:
            oldest = _rate_limit_store[client_ip][0]
            retry_after = int(_RATE_LIMIT_WINDOW - (now - oldest)) + 1
            logger.warning("rate_limit_exceeded", client_ip=client_ip)
            return Response(
                content='{"error":"Too many requests","detail":"Rate limit exceeded"}',
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "Content-Type": "application/json",
                },
            )

        _rate_limit_store[client_ip].append(now)
        return await call_next(request)


def add_cors_middleware(app: object, allowed_origins: list[str] | None = None) -> None:
    """Attach CORS middleware to the FastAPI app."""
    origins = allowed_origins or ["http://localhost:3000", "http://127.0.0.1:3000"]
    app.add_middleware(  # type: ignore[attr-defined]
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )