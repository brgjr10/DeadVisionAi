"""
Episodic memory — per-session conversation history.
Backed by Redis for fast in-session access.
"""
from __future__ import annotations

import json
from typing import Optional

from app.cache.redis_cache import get_redis_cache
from app.observability.logging_config import get_logger

logger = get_logger(__name__)

_SESSION_KEY_PREFIX = "episodic:"
_DEFAULT_TTL = 86400  # 24 hours


class EpisodicMemory:
    """
    Stores and retrieves per-session conversation history using Redis.
    Each session has a list of message dicts: {"role": ..., "content": ...}
    """

    async def store(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session's episodic memory."""
        cache = get_redis_cache()
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        try:
            client = await cache._get_client()
            message = json.dumps({"role": role, "content": content})
            await client.rpush(key, message)
            await client.expire(key, _DEFAULT_TTL)
            logger.debug("episodic_stored", session_id=session_id, role=role)
        except Exception as exc:
            logger.warning("episodic_store_error", session_id=session_id, error=str(exc))

    async def get(self, session_id: str, limit: int = 50) -> list[dict]:
        """
        Retrieve the most recent `limit` messages for a session.
        Returns an empty list if the session has no history.
        """
        cache = get_redis_cache()
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        try:
            client = await cache._get_client()
            # Get last `limit` messages
            raw_messages = await client.lrange(key, -limit, -1)
            messages = []
            for raw in raw_messages:
                try:
                    messages.append(json.loads(raw))
                except Exception:
                    continue
            return messages
        except Exception as exc:
            logger.warning("episodic_get_error", session_id=session_id, error=str(exc))
            return []

    async def get_all(self, session_id: str) -> list[dict]:
        """Retrieve all messages for a session."""
        cache = get_redis_cache()
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        try:
            client = await cache._get_client()
            raw_messages = await client.lrange(key, 0, -1)
            return [json.loads(r) for r in raw_messages if r]
        except Exception as exc:
            logger.warning("episodic_get_all_error", session_id=session_id, error=str(exc))
            return []

    async def clear(self, session_id: str) -> None:
        """Clear all episodic memory for a session."""
        cache = get_redis_cache()
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        await cache.delete(key)
        logger.debug("episodic_cleared", session_id=session_id)

    async def count(self, session_id: str) -> int:
        """Return the number of messages stored for a session."""
        cache = get_redis_cache()
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        try:
            client = await cache._get_client()
            return await client.llen(key)
        except Exception:
            return 0


_episodic_instance: Optional[EpisodicMemory] = None


def get_episodic_memory() -> EpisodicMemory:
    """Return the singleton EpisodicMemory instance."""
    global _episodic_instance
    if _episodic_instance is None:
        _episodic_instance = EpisodicMemory()
    return _episodic_instance
