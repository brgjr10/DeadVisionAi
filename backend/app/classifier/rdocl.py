"""
rdocl — Runtime Detection of Classifier model changes.

Two independent watchers keep the local classifier honest:

1. **ModelVersionDetector**
   Polls LM Studio `/v1/models` every `DETECT_INTERVAL` seconds.
   Stores the current `loaded_model_id` in Redis with a TTL equal to the poll
   interval × 2.  On the next poll, if the stored id differs from the live
   response, `classifier:version_changed` key is set and the local-classify
   path is demoted until the new model is proven stable.

2. **SchemaHealthCheck**
   Sends a lightweight probe prompt to the local model once per interval.
   The probe's expected output is a fixed JSON blob.  If the live model
   returns anything that cannot be parsed into the `TaskClassification`
   schema, `classifier:schema_mismatch` is set.

Both signals are consumed by `_classify_with_local_model`: if either key
is present the call returns `None` immediately, routing straight to
`_heuristic_classify` without hammering the local endpoint.

All state lives in Redis with short TTLs so the system survives a restart
without stale locks.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Redis key names ────────────────────────────────────────────────────────
_KEY_VERSION_LOCK = "rdocl:version_lock"     # set → demoted
_KEY_VERSION_SNAP = "rdocl:version_snapshot" # current known model id
_KEY_SCHEMA_LOCK = "rdocl:schema_lock"       # set → schema invalid
_KEY_SCHEMA_SNAP = "rdocl:schema_snapshot"   # JSON of last good probe result

# ── Defaults ───────────────────────────────────────────────────────────────
_DEFAULT_INTERVAL  = 60          # seconds between polls
_DEFAULT_TTL       = 120         # seconds; must be > interval
_DEFAULT_TIMEOUT   = 6.0         # seconds for /v1/models call
_PROMPT_HINT       = "output json with keys: intent, complexity_score, estimated_tokens, recommended_tools, tool_only_flag, confidence"

_EXPECTED_SCHEMA_KEYS = frozenset({
    "intent",
    "complexity_score",
    "estimated_tokens",
    "recommended_tools",
    "tool_only_flag",
    "confidence",
})


# ── helpers ────────────────────────────────────────────────────────────────

def _schema_is_valid(raw: str) -> bool:
    """Return True when *raw* parses as JSON and carries all expected keys."""
    try:
        obj = json.loads(raw)
        return _EXPECTED_SCHEMA_KEYS.issubset(obj.keys())
    except (json.JSONDecodeError, AttributeError):
        return False


def _hash_model_id(model_id: str) -> str:
    return hashlib.sha256(model_id.encode()).hexdigest()[:16]


# ── ModelVersionDetector ───────────────────────────────────────────────────

class ModelVersionDetector:
    """
    Background watcher that detects when LM Studio loads a different model.

    On every poll:
      1. GET {base_url}/v1/models
      2. Extract the first loaded model id
      3. Compare against the Redis-stored snapshot
      4. If changed → set ``rdocl:version_changed`` and update the snapshot
      5. If healthy → delete ``rdocl:version_changed`` (promoting classify recover)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: str = "lm-studio",
        interval: int = _DEFAULT_INTERVAL,
        ttl: int = _DEFAULT_TTL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        if self._base_url.endswith("/v1"):
            self._base_url = self._base_url[:-3]
        self._api_key = api_key
        self._interval = interval
        self._ttl = ttl
        self._timeout = timeout
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            logger.info("rdocl_version_detector_started")

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("rdocl_version_detector_stopped")

    # ── public API ──────────────────────────────────────────────────────────

    async def get_current_model_id(self) -> Optional[str]:
        """One-shot read: return the live model id or None."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/v1/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                models = data.get("data", [])
                if not models:
                    return None
                first = models[0]
                return first.get("id") or first.get("model")
        except Exception as exc:
            logger.warning("rdocl_version_detect_failed", error=str(exc))
            return None

    def is_demoted(self) -> bool:
        """True when a version-change has been detected and not yet recovered."""
        cache = self._get_cache()
        try:
            return bool(cache.get(_KEY_VERSION_LOCK))
        except Exception:
            return False

    # ── internal ────────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("rdocl_poll_loop_error", error=str(exc))
            await asyncio.sleep(self._interval)

    async def _run_once(self) -> None:
        live_id = await self.get_current_model_id()
        if live_id is None:
            return  # LM Studio offline; don't flip the lock

        cache = self._get_cache()
        stored = cache.get(_KEY_VERSION_SNAP)

        if stored and stored != live_id:
            logger.warning(
                "rdocl_model_version_changed",
                old=stored[:64],
                new=live_id[:64],
            )
            cache.set(_KEY_VERSION_LOCK, "1", ex=self._ttl)
            cache.set(_KEY_VERSION_SNAP, live_id, ex=self._ttl)
            # Also invalidate the schema cache — new model means new behaviour
            cache.delete(_KEY_SCHEMA_LOCK)
            cache.delete(_KEY_SCHEMA_SNAP)
        elif not stored:
            cache.set(_KEY_VERSION_SNAP, live_id, ex=self._ttl)
        else:
            # Healthy — clear any stale version-changed lock
            cache.delete(_KEY_VERSION_LOCK)

    @staticmethod
    def _get_cache():
        """Lazy import redis cache to avoid circular imports."""
        from app.cache.redis_cache import get_redis_cache
        return get_redis_cache()


# ── SchemaHealthCheck ───────────────────────────────────────────────────────

class SchemaHealthCheck:
    """
    Background watcher that validates the local classifier model's output
    against the expected TaskClassification JSON schema.

    Sends a constant probe prompt; if the parsed output is missing any of the
    six required keys, ``rdocl:schema_mismatch`` is set in Redis and the
    local-classify path is demoted until the next healthy probe.
    """

    _PROBE_PROMPT = (
        'Classify this task and output JSON only: "what is 2+2?". '
        'Keys: intent, complexity_score, estimated_tokens, recommended_tools, '
        'tool_only_flag, confidence.'
    )

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: str = "lm-studio",
        model: str = "qwen2.5-0.5b-instruct",
        interval: int = _DEFAULT_INTERVAL,
        ttl: int = _DEFAULT_TTL,
        timeout: float = 5.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        if self._base_url.endswith("/v1"):
            self._base_url = self._base_url[:-3]
        self._api_key = api_key
        self._model = model
        self._interval = interval
        self._ttl = ttl
        self._timeout = timeout
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            logger.info("rdocl_schema_health_check_started")

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("rdocl_schema_health_check_stopped")

    # ── public API ──────────────────────────────────────────────────────────

    def is_demoted(self) -> bool:
        """True when schema health check has failed recently."""
        cache = self._get_cache()
        try:
            return bool(cache.get(_KEY_SCHEMA_LOCK))
        except Exception:
            return False

    # ── internal ────────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._probe()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("rdocl_schema_probe_error", error=str(exc))
            await asyncio.sleep(self._interval)

    async def _probe(self) -> None:
        cache = self._get_cache()
        url = f"{self._base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": self._PROBE_PROMPT}],
                        "temperature": 0,
                        "max_tokens": 120,
                    },
                )
                if resp.status_code != 200:
                    logger.warning(
                        "rdocl_schema_probe_http_error",
                        status=resp.status_code,
                    )
                    return

                data = resp.json()
                raw = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

            if _schema_is_valid(raw):
                cache.set(_KEY_SCHEMA_SNAP, raw, ex=self._ttl)
                cache.delete(_KEY_SCHEMA_LOCK)          # healthy — promote
                cache.delete(_KEY_SCHEMA_MISMATCH)
            else:
                logger.warning(
                    "rdocl_schema_mismatch_detected",
                    raw_preview=raw[:200],
                )
                cache.set(_KEY_SCHEMA_LOCK, "1", ex=self._ttl)

        except Exception as exc:
            logger.warning("rdocl_schema_probe_failed", error=str(exc))

    @staticmethod
    def _get_cache():
        from app.cache.redis_cache import get_redis_cache
        return get_redis_cache()


# ── Singleton instances ─────────────────────────────────────────────────────

_detector: Optional[ModelVersionDetector] = None
_health: Optional[SchemaHealthCheck] = None


def get_version_detector(
    base_url: str = "http://localhost:8080",
    api_key: str = "lm-studio",
    interval: int = _DEFAULT_INTERVAL,
) -> ModelVersionDetector:
    global _detector
    if _detector is None:
        _detector = ModelVersionDetector(base_url=base_url, api_key=api_key, interval=interval)
    return _detector


def get_schema_health_check(
    base_url: str = "http://localhost:8080",
    api_key: str = "lm-studio",
    model: str = "qwen2.5-0.5b-instruct",
    interval: int = _DEFAULT_INTERVAL,
) -> SchemaHealthCheck:
    global _health
    if _health is None:
        _health = SchemaHealthCheck(base_url=base_url, api_key=api_key, model=model, interval=interval)
    return _health


# ── Combined gate ─────────────────────────────────────────────────────────

def is_local_classify_available() -> bool:
    """Return True only when neither the version lock nor the schema lock is set."""
    try:
        cache = _detector._get_cache() if _detector else _health._get_cache()
    except Exception:
        return True   # Redis unavailable → assume healthy (no blocking)

    version_blocked  = bool(cache.get(_KEY_VERSION_LOCK))
    schema_blocked   = bool(cache.get(_KEY_SCHEMA_LOCK))
    return not (version_blocked or schema_blocked)
