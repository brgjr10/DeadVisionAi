"""
Redis cache implementation for HAIOS.
Supports key/value caching with TTL, tag-based invalidation, and metrics.
"""
from __future__ import annotations

import json
from typing import Optional

import redis.asyncio as aioredis

from app.config import get_settings
from app.observability.logging_config import get_logger
from app.observability.metrics import cache_evictions_total, cache_hits_total, cache_misses_total

logger = get_logger(__name__)

_TAG_PREFIX = "tag:"
_CACHE_TYPE = "exact"


class RedisCache:
    """
    Async Redis cache with TTL, tag-based invalidation, and Prometheus metrics.
    """

    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0

    async def _get_client(self) -> aioredis.Redis:
        """Return the Redis client, creating it if necessary."""
        if self._client is None:
            settings = get_settings()
            self._client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def get(self, key: str) -> Optional[str]:
        """
        Retrieve a cached value by key.
        Returns None on cache miss or Redis unavailability.
        """
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value is not None:
                self._hit_count += 1
                cache_hits_total.labels(cache_type=_CACHE_TYPE).inc()
                logger.debug("cache_hit", key=key)
                return value
            else:
                self._miss_count += 1
                cache_misses_total.labels(cache_type=_CACHE_TYPE).inc()
                logger.debug("cache_miss", key=key)
                return None
        except Exception as exc:
            logger.warning("redis_get_error", key=key, error=str(exc))
            return None

    async def set(self, key: str, value: str, ttl: int = 0) -> None:
        """
        Store a value in the cache with an optional TTL (seconds).
        TTL=0 means no expiry.
        """
        try:
            client = await self._get_client()
            if ttl > 0:
                await client.setex(key, ttl, value)
            else:
                await client.set(key, value)
            logger.debug("cache_set", key=key, ttl=ttl)
        except Exception as exc:
            logger.warning("redis_set_error", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        """Delete a single cache entry."""
        try:
            client = await self._get_client()
            await client.delete(key)
            logger.debug("cache_delete", key=key)
        except Exception as exc:
            logger.warning("redis_delete_error", key=key, error=str(exc))

    async def delete_by_tag(self, tag: str) -> None:
        """
        Delete all cache entries associated with a tag.
        Tags are stored as Redis sets: tag:<tag> → set of keys.
        """
        try:
            client = await self._get_client()
            tag_key = f"{_TAG_PREFIX}{tag}"
            keys = await client.smembers(tag_key)
            if keys:
                pipe = client.pipeline()
                for key in keys:
                    pipe.delete(key)
                pipe.delete(tag_key)
                await pipe.execute()
                self._eviction_count += len(keys)
                cache_evictions_total.inc(len(keys))
                logger.info("cache_tag_invalidated", tag=tag, keys_deleted=len(keys))
        except Exception as exc:
            logger.warning("redis_delete_by_tag_error", tag=tag, error=str(exc))

    async def set_with_tag(self, key: str, value: str, tag: str, ttl: int = 0) -> None:
        """Store a value and associate it with a tag for bulk invalidation."""
        await self.set(key, value, ttl)
        try:
            client = await self._get_client()
            tag_key = f"{_TAG_PREFIX}{tag}"
            await client.sadd(tag_key, key)
            if ttl > 0:
                await client.expire(tag_key, ttl)
        except Exception as exc:
            logger.warning("redis_set_tag_error", key=key, tag=tag, error=str(exc))

    async def invalidate_pattern(self, pattern: str) -> None:
        """
        Delete all keys matching a glob pattern.
        Use with caution — scans the entire keyspace.
        """
        try:
            client = await self._get_client()
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
                self._eviction_count += len(keys)
                cache_evictions_total.inc(len(keys))
                logger.info("cache_pattern_invalidated", pattern=pattern, keys_deleted=len(keys))
        except Exception as exc:
            logger.warning("redis_invalidate_pattern_error", pattern=pattern, error=str(exc))

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_stats(self) -> dict:
        """Return cache statistics."""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0.0
        return {
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "eviction_count": self._eviction_count,
            "hit_rate": round(hit_rate, 4),
        }


_redis_cache_instance: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """Return the singleton RedisCache instance."""
    global _redis_cache_instance
    if _redis_cache_instance is None:
        _redis_cache_instance = RedisCache()
    return _redis_cache_instance
