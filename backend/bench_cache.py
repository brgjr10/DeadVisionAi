"""Extended benchmark — cache hit test + cold start test."""
import asyncio, time, httpx, json, statistics

LMSTUDIO_URL = "http://localhost:1234/chat/completions"
LMSTUDIO_KEY = "sk-lm-oWIgaJqa:EzedWIId47dvcYlduV2H"
CLASSIFIER_MODEL = "qwen2.5-0.5b-instruct"

SYSTEM_PROMPT = """You are a routing classifier.
Return ONLY valid JSON with these keys:
  category: one of: simple, coding, complex, huge_context
  reason: short reason string"""

UNIQUE_PROMPTS = [
    "What is 2+2?",
    "Write a Python function to reverse a list",
    "Explain how async/await works in Python",
    "Summarize the key points of functional programming",
    "Search for latest news about AI",
    "Read the contents of config.yaml",
    "Run npm install in the project directory",
    "What did I say about Redis yesterday?",
    "First gather requirements, then implement the feature, finally write tests",
    "Debug this error: IndexError list index out of range",
]


async def bench_unique(n_rounds=2):
    """Round 1 = all unique (cache miss), Round 2 = same prompts again (should be cache hits)."""
    headers = {"Authorization": f"Bearer {LMSTUDIO_KEY}", "Content-Type": "application/json"}
    r1, r2 = [], []
    for round_idx in range(n_rounds):
        bucket = r1 if round_idx == 0 else r2
        for prompt in UNIQUE_PROMPTS:
            payload = {
                "model": CLASSIFIER_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 35,
            }
            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.post(LMSTUDIO_URL, json=payload, headers=headers)
                dt = (time.perf_counter() - t0) * 1000
                bucket.append(dt)
            except Exception:
                pass
    return r1, r2


async def check_redis():
    """Read clf_cache:* keys from Redis and report stats."""
    try:
        from app.cache.redis_cache import get_redis_cache
        cache = get_redis_cache()
        # We can't SCAN via the simple wrapper; use key pattern via info
        info = cache._get_client().info("keyspace")
        return info
    except Exception as e:
        return str(e)


async def main():
    print("=== Unique round (all cache miss) ===")
    r1, r2 = await bench_unique(2)
    if r1:
        s1 = sorted(r1)
        print(f"  n={len(r1)}  min={s1[0]:.0f}ms  median={s1[len(s1)//2]:.0f}ms  "
              f"max={s1[-1]:.0f}ms  avg={statistics.mean(r1):.0f}ms")

    print("\n=== Repeat round (10 identical prompts — should be cache hits) ===")
    if r2:
        s2 = sorted(r2)
        print(f"  n={len(r2)}  min={s2[0]:.0f}ms  median={s2[len(s2)//2]:.0f}ms  "
              f"max={s2[-1]:.0f}ms  avg={statistics.mean(r2):.0f}ms")

    speedup = statistics.mean(r1) / statistics.mean(r2) if r1 and r2 and statistics.mean(r2) > 0 else 0
    print(f"\n  Cache speedup: {speedup:.1f}x")

    print(f"\n=== Redis check ===")
    info = await check_redis()
    print(f"  {info}")


asyncio.run(main())
