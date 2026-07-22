"""
Utility functions for local model routing and classification.
"""
import os
import json
from typing import Optional
import httpx

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:8080")
# Normalise: strip trailing / and /v1 suffix so we always construct
# the canonical path: {base}/v1/chat/completions
_norm = LMSTUDIO_BASE_URL.rstrip("/")
if _norm.endswith("/v1"):
    _norm = _norm[:-3]
LMSTUDIO_BASE_URL = _norm    # now always http://localhost:8080 (no /v1)
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "qwen2.5-0.5b-instruct")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lm-studio")

# Fast lightweight classifier model — override with CLASSIFIER_MODEL env var
LOCAL_CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "qwen2.5-0.5b-instruct")

# Classification result cache TTL (seconds)
CLASSIFY_CACHE_TTL = int(os.getenv("CLASSIFY_CACHE_TTL", "600"))   # 10 minutes

# Keep-alive ping interval for the classifier model (seconds)
CLASSIFIER_KEEPALIVE_INTERVAL = int(os.getenv("CLASSIFIER_KEEPALIVE_INTERVAL", "30"))  # 30 seconds

# Better local reasoning model
LOCAL_GENERAL_MODEL = LMSTUDIO_MODEL

# Vision model
LOCAL_VISION_MODEL = "llava-v1.5-7b"

# Token thresholds
SIMPLE_TOKEN_LIMIT = 80
COMPLEX_TOKEN_LIMIT = 500
HUGE_CONTEXT_LIMIT = 12000


async def is_classify_available() -> bool:
    """
    Return True only when neither rdocl version-lock nor schema-lock is set.

    Reads two Redis keys set by rdocl.py:
      - ``rdocl:version_lock``  → model was swapped, demote classify path
      - ``rdocl:schema_lock``   → schema drift detected, demote classify path

    If Redis is unavailable we fail-open: the actual classify call will
    surface any transport errors naturally.
    """
    try:
        from app.cache.redis_cache import get_redis_cache

        cache = get_redis_cache()
        if await cache.get("rdocl:version_lock") or await cache.get("rdocl:schema_lock"):
            return False
    except Exception:
        pass
    return True


async def call_local_model(prompt: str, model: Optional[str] = None) -> str:
    """
    LM Studio local model call (async version).
    """
    if model is None:
        model = LMSTUDIO_MODEL

    headers = {
        "Authorization": f"Bearer {LMSTUDIO_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{LMSTUDIO_BASE_URL}/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def local_classify(prompt: str) -> dict:
    """
    Tiny local classifier using LM Studio (async version).
    Returns a dictionary with keys: category and reason.

    Reads rdocl version-lock and schema-lock from Redis before calling
    the local endpoint.  If either lock is set, returns a safe fallback
    immediately without hitting LM Studio.

    1. Check Redis result cache first (10 min TTL) — skips LM Studio entirely on cache hit.
    2. Call LM Studio with reduced max_tokens (35) for fastest possible response.
    3. Store result in Redis on success.
    """
    if not await is_classify_available():
        return {
            "category": "complex",
            "reason": "classify_demoted_by_rdocl",
        }

    # 1. Result cache — skip LM Studio on cache hit
    cached = await _get_cached_classification(prompt)
    if cached is not None:
        return cached

    system_prompt = """
You are a routing classifier.

Return ONLY valid JSON:

{
  "category": "simple|coding|complex|huge_context",
  "reason": "short reason"
}
"""

    headers = {
        "Authorization": f"Bearer {LMSTUDIO_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LOCAL_CLASSIFIER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "max_tokens": 35    # was 60 — the 4 possible categories are single words
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{LMSTUDIO_BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            # Strip markdown code fences if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            result = json.loads(content)
            # 3. Cache the result
            await _set_cached_classification(prompt, result)
            return result
    except Exception:
        return {
            "category": "complex",
            "reason": "fallback"
        }


async def _get_cached_classification(prompt: str) -> Optional[dict]:
    """Get cached classification result from Redis."""
    try:
        from app.cache.redis_cache import get_redis_cache
        import hashlib
        import json
        cache = get_redis_cache()
        key = f"classify:{hashlib.md5(prompt.encode()).hexdigest()}"
        cached = await cache.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    return None


async def _set_cached_classification(prompt: str, result: dict) -> None:
    """Cache classification result in Redis."""
    try:
        from app.cache.redis_cache import get_redis_cache
        import hashlib
        import json
        cache = get_redis_cache()
        key = f"classify:{hashlib.md5(prompt.encode()).hexdigest()}"
        # Serialize dict to JSON string
        value_json = json.dumps(result)
        await cache.set(key, value_json, ttl=CLASSIFY_CACHE_TTL)
    except Exception:
        pass