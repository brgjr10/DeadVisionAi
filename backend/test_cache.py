"""Verify cache roundtrip for routing_helper."""
import asyncio, json
from app.cache.redis_cache import get_redis_cache
from app.utils.routing_helper import _classify_cache_key, _set_cached_classification, _get_cached_classification


async def main():
    cache = get_redis_cache()

    # 1. Direct cache roundtrip
    key = "test_classify_bench"
    await cache.set(key, json.dumps({"category": "simple", "reason": "test"}), ttl=60)
    val = await cache.get(key)
    print(f"Raw Redis set/get: {val}")
    await cache.delete(key)

    # 2. Helper roundtrip
    result = {"category": "simple", "reason": "benchmark_test"}
    await _set_cached_classification("hello world test prompt", result)
    ck = _classify_cache_key("hello world test prompt")
    print(f"Cache key: clf_cache:{ck}")
    raw = await cache.get(f"clf_cache:{ck}")
    print(f"Direct Redis get: {raw}")
    cached = await _get_cached_classification("hello world test prompt")
    print(f"Helper roundtrip: {cached}")

    # 3. Cleanup
    await cache.delete(f"clf_cache:{ck}")


asyncio.run(main())
