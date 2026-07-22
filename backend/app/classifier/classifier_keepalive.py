"""
Classifier model keep-alive.

LM Studio unloads idle models from GPU/CPU memory after a few seconds of
inactivity.  The first token on the next real request then pays the full
reload cost (250–500 ms for qwen2.5-0.5b-instruct on consumer hardware).

This module sends a tiny empty completion to the classifier model every
``CLASSIFIER_KEEPALIVE_INTERVAL`` seconds so it never goes idle.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

import httpx

from app.config import get_settings
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class ClassifierKeepAlive:
    """
    Background watcher that nudges the local classifier model with a
    token-free completion on a fixed interval, preventing LM Studio from
    offloading it from GPU/CPU memory.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: str = "lm-studio",
        model: str = "qwen2.5-0.5b-instruct",
        interval: int = 30,       # seconds
        timeout: float = 4.0,
    ) -> None:
        # Normalize: ensure we have the base URL without /v1 suffix for construction
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            normalized = normalized[:-3]
        self._base_url = normalized
        self._api_key = api_key
        self._model = model
        self._interval = interval
        self._timeout = timeout
        self._task: Optional[asyncio.Task] = None
        self._running = False

    # ── lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._ping_loop())
            logger.info(
                "classifier_keepalive_started",
                model=self._model,
                interval=self._interval,
            )

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("classifier_keepalive_stopped")

    # ── internal ─────────────────────────────────────────────────────────────

    async def _ping_loop(self) -> None:
        """Maintain the model in memory with recurring empty completions."""
        # First ping immediately so the model is warm on process start
        await self._ping()

        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if not self._running:
                    break
                await self._ping()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("classifier_keepalive_ping_error", error=str(exc))
                await asyncio.sleep(self._interval)

    async def _ping(self) -> None:
        """Send a zero-token completion to keep the model resident."""
        url = f"{self._base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": ""}],
            "max_tokens": 1,
            "stream": False,
        }
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                ms = (time.perf_counter() - t0) * 1000
                if resp.status_code == 200:
                    logger.debug("classifier_keepalive_ok", ms=round(ms, 1))
                else:
                    logger.warning(
                        "classifier_keepalive_http_error",
                        status=resp.status_code,
                        ms=round(ms, 1),
                    )
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000
            logger.debug(
                "classifier_keepalive_failed",
                error=str(exc),
                ms=round(ms, 1),
            )


# ── singleton ────────────────────────────────────────────────────────────────

_instance: Optional[ClassifierKeepAlive] = None


def get_classifier_keepalive(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    interval: Optional[int] = None,
) -> ClassifierKeepAlive:
    global _instance
    if _instance is None:
        settings = get_settings()
        _instance = ClassifierKeepAlive(
            base_url=base_url or settings.lmstudio_base_url,
            api_key=api_key or settings.lmstudio_api_key,
            model=model or os.getenv("CLASSIFIER_MODEL", "qwen2.5-0.5b-instruct"),
            interval=interval or int(os.getenv("CLASSIFIER_KEEPALIVE_INTERVAL", "30")),
        )
    return _instance
