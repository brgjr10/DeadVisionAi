# HAIOS — Backend Improvements Audit

> Generated after full codebase exploration. Every item links to a specific file and a concrete problem found in the current code.

---

## CRITICAL — Break-If-Not-Fixed

### 1. No Actual Quota Tracking on Any Provider (Total Guard-Rail Failure)
**Files:** `config.py`, `optimizer.py`, `scoring.py`, `master_router.py`

Every `quota_limit` value is the same hardcoded `1_000_000` placeholder. The system has no real connection to provider APIs to query actual consumed tokens, remaining RPD/RPM limits, or billable spend. `_HARD_LIMIT_PCT = 0.95` fires on a fiction, not a real budget alarm.

**Fix:** Wire each provider adapter to read quota from the official provider admin API (e.g. OpenRouter `/api/v1/auth/key`, Groq `/v1/usage`, Gemini `/v1beta/usage`, etc.) each health-cycle. Store the returned `limit` and `usage` fields in `ProviderBase._quota_limit` / `_token_count`. `optimizer.py::_compute_quota_remaining` must subtract real spend, not local counter.

### 2. No Free-Tier Whitelist — System Will Route to Any Provider
**File:** `master_router.py` (lines 32–54)

`_CLOUD_FALLBACK_ORDER` and `_PROVIDER_DEFAULT_MODELS` contain paid providers (OpenAI, Anthropic, Together, Fireworks) with no condition checking whether the configured key belongs to a free account. The `_cost_score` in `scoring.py` scores them as competitive options regardless of whether they are on a free or paid plan.

**Fix:** Add `get_settings().free_tier_only` flag (default `true`). Build a `_FREE_PROVIDERS` set: `{"groq", "openrouter:free-tagged-models", "gemini", "deepseek"}`. Any provider not in the set is ignored for routing until manually opted-in. `config.py::get_configured_providers()` must emit a warning on startup for any non-whitelisted key and set `in_cooldown = True` for it until the user explicitly overrides.

### 3. Classifier Calls 9 Separate Cloud APIs Before Heuristics Fire
**File:** `classifier.py` (lines 737–819)

The `classify()` fallback chain runs OpenRouter → Groq → Gemini → DeepSeek → Together → Fireworks → OpenAI → Anthropic before ever reaching `_heuristic_classify`. Under load, a burst of 100 chat requests can generate 900 external API calls purely for classification. This exhausts free-tier rate limits in minutes and creates unnecessary spend.

**Fix:** Collapse classifier to a two-tier fallback: (1) local LM Studio `local_classify`, (2) one cloud call with extreme backpressure, (3) heuristic-only. Cache classification results per `(prompt-hash, intent)` for 24 h in Redis so the same question never wastes a classification API call twice.

### 4. Semantic Cache Is O(n) Linear Scan — Dies with Any Volume
**File:** `semantic_cache.py` (lines 118–129)

The `lookup` method iterates over every embedding key in the Redis index, unpacks JSON, and computes cosine similarity in Python. With 10 000 stored prompts (the index cap at line 184), each lookup fires ~10 000 Redis `GET` calls. This blocks the event loop for seconds, starves concurrency, and makes the semantic cache a net liability at any real traffic level.

**Fix:** Replace linear scan with Qdrant vector index. Store the cache embeddings as a distinct Qdrant collection (`semantic_cache_embeddings`) using the existing `VectorStore` client. `lookup` becomes a single `search()` call returning the top match in < 5 ms. Drop `sentence-transformers` from `requirements.txt` for cache-only deployments; use Qdrant's on-server embedding filter instead.

### 5. Health Check Only Tests HTTP-200 — Doesn't Validate Model Availability
**Files:** `lmstudio_provider.py` (lines 150–157), `ollama_provider.py` (lines 134–141)

Both `health_check()` methods hit `/models` or `/api/tags` and return `True` on any 200 response. A loaded LM Studio instance that has OOM-killed the model thread still returns 200; a rate-limited Ollama daemon returns 200. Health checks that only verify "server is running" give the router a false green light and send traffic to a broken provider.

**Fix:** Add a "probe" sub-step: `POST /chat/completions` with `max_tokens=1` and a 2 s timeout. If the probe returns an error or takes > 2 s, mark the provider unhealthy. In LM Studio specifically, check the loaded model list response and confirm the expected model ID is present before returning `True`.

---

## HIGH — Fix Before Scaling

### 6. Local Sessions Bypass the Global Rate Limiter
**File:** `middleware.py` (lines 93–121)

`RateLimitMiddleware` is only applied to the FastAPI HTTP layer via `app.add_middleware`. The WebSocket streaming path (`router.py` → `/ws` handler) and the in-process `call_local_model` path in `routing_helper.py` bypass it entirely. A single session opening 50 concurrent tool+LLM calls floods local LM Studio with no back-pressure.

**Fix:** Apply a local concurrency semaphore in `lmstudio_provider.py` and `ollama_provider.py` — defaulting to `asyncio.Semaphore(4)` for each provider — so that regardless of entry point, at most 4 simultaneous inference requests hit LM Studio at once. Add a per-session `asyncio.Queue` cap (max 10 pending requests).

### 7. Token Counter Is a Local Variable — No Persistent Monthly Budget
**File:** `optimizer.py` (lines 36–44, 80–87)

`token_count` is stored per-process. If the backend restarts, all consumption records are zeroed. There is no "monthly spend budget" — the cooldown logic resets every health poll, not every billing cycle. A provider configured as "free tier" can receive 10 000 calls on day 1 and still show `quota_remaining = 1.0` on day 2.

**Fix:** Persist usage counters in Redis (no DB dependency). On startup and every 60 s, load from Redis. Add `monthly_spend_limit` (default 0.00 for free-tier-only mode) and a `PROVIDER_SPEND_LIMITS` env block per provider. `optimizer.py::_compute_quota_remaining` must read from Redis counters, not in-process state.

### 8. Memory Stores Facts Indefinitely — Unbounded Qdrant and Redis Growth
**File:** `memory/manager.py` (lines 52–67)

`store_semantic` calls `VectorStore.upsert` with no TTL, no max-facts cap, and no deduplication. Every run of every agent tool upserts to Qdrant. Over a week this produces tens of thousands of vectors. Similarly `EpisodicMemory` stores per-session messages in Redis with no expiry set in `store()`.

**Fix:** Add `semantic_facts_max: int = 10_000` and `episodic_ttl_seconds: int = 86400` to `Settings`. In `memory/manager.py::store_semantic`, prune oldest facts when the collection exceeds the cap. Set per-key TTL on Redis episodic entries. In `summarize_session`, actually run an LLM summarization call instead of the comment-only placeholder.

### 9. LM Studio Provider Ignores GPU Offload / KV-Cache Settings
**File:** `lmstudio_provider.py`

The provider passes no generation parameters (`max_tokens`, `temperature_min_p`, `repeat_penalty`) and uses a fixed 120 s timeout. LM Studio is being used as a generic OpenAI-socket wrapper without configuring GPU offload layers, context window, or meta-request headers that LM Studio accepts (`X-LM-Studio-GPU-Layers`, `X-LM-Studio-Ctx-Size`).

**Fix:** Add an optional `LMSTUDIO_GPU_LAYERS`, `LMSTUDIO_CTX_SIZE`, `LMSTUDIO_GPU_OFFLOAD_V1` block to `.env` and inject them as headers in the `_full_complete` and `_stream_complete` methods. Expose them as optional payload fields (`max_tokens`, `temperature`, `repeat_penalty`) driven from `Settings`. Default to a 4096 context window, opt-in to 8192 or 32k only when explicitly set.

### 10. `_jet_brains` In-Memory Rate Limiter Is Process-Bound
**File:** `middleware.py` (lines 22–24)

`_rate_limit_store` is a `defaultdict(list)` inside the module. On multi-worker deployment (`uvicorn --workers 4`) each worker gets its own independent bucket — the effective rate limit is multiplied by the number of workers. On restart, all counters reset to zero.

**Fix:** Replace with Redis-backed sliding-window counter using sorted sets (the canonical pattern: `ZADD rate:{ip} {timestamp} {reqId}`, `ZREMRANGEBYSCORE`, `ZCARD`). This is consistent with the existing Redis infrastructure and works correctly across workers.

### 11. Provider Quota Remains Hardcoded — Scoring Is Not Real
**File:** `optimizer.py` (line 43)

`quota_limit: 1_000_000` is a legacy default with no connection to reality. A provider returning HTTP 429 technically sets cooldown, but the `scoring.py` weighted formula (`0.35 × quota_pct`) inverts at the wrong moment when a provider silently drains quota without returning 429 (some OpenAI-compatible APIs return HTTP 200 with an error body).

**Fix:** In every provider adapter, parse the HTTP response body for `error.code === "insufficient_quota"` and `error.code === "rate_limit_exceeded"` and treat them identically to 429. Update `ProviderBase._quota_remaining_pct` from response headers (`X-RateLimit-Remaining`) when present, not only from cooldown events.

### 12. `Router.py` Chat Endpoint Silently Swallows Provider Routing Errors
**File:** `router.py` (lines 159–164)

When the master router raises `RoutingError` (all providers exhausted), the `except` branch returns `{"error": str(exc)}` with HTTP 500. The calling frontend shows a generic "Server error" with no guidance. The attempted providers and reasons are never surfaced, so the admin cannot diagnose whether the failure was a real outage or a configuration gap.

**Fix:** Include `attempted_providers`, `reasons`, and `health_registry_snapshot` in every 500 response body (structured, not just `str(exc)`). Add a `/api/v1/routing-debug` endpoint (internal-only) that returns the current health registry, scoring table, and cooldown state so an admin can see exactly why a request was not routed.

### 13. OpenRouter Key Used for Classification on Every Single Request
**File:** `classifier.py` (lines 135–206)

Even when both `_classify_with_local_model` and `_check_ollama` succeed, the classifier's fallback chain still tries the 8 free OpenRouter models *sequentially* on the first failure before dropping to heuristics. The 10 s timeout per call means the classifier can take 80+ s in the absolute worst case before falling through.

**Fix:** Add a global 500 ms classification budget. If the local LM Studio call succeeds, skip all cloud classifiers. If Ollama is reachable, skip OpenRouter and all subsequent cloud calls. Only attempt one cloud call maximum, and only if `(local_failed AND ollama_unreachable)`.

---

## MEDIUM — Fix Before Production Hardening

### 14. `LMSTUDIO_GPU_LAYERS` and Context Window Not Split by Model
**File:** `requirements.txt`

`sentence-transformers` pulls in PyTorch with a default CUDA/CPU build that adds ~2 GB of RAM overhead. When using LM Studio for local inference, PyTorch is already managed by LM Studio's separate process; the sentence-transformers import in `semantic_cache.py` loads a second independent copy of the CPU embedder inside the backend.

**Fix:** Make sentence-transformers fully optional at install time. Split into an extras group `[embeddings]` in `pyproject.toml`. When `SEMANTIC_CACHE_ENABLED=false` or encoder load fails, short-circuit all semantic cache paths to a direct Redis hash-lookup; never load the transformer.

### 15. `routing_helper.py` Imports at Module Level — Side-Effects on Import
**File:** `routing_helper.py` (lines 9–11)

`from dotenv import load_dotenv` and `load_dotenv()` execute at import time. If the backend is deployed as a packaged wheel, `dotenv` is the wrong mechanism; the import silently succeeds in production even when no `.env` is present, which masks misconfiguration.

**Fix:** Remove `load_dotenv()` from `routing_helper.py`. Load env only in `config.py` (which already uses Pydantic Settings and a proper `env_file` path). This file is a utility module — it must not have side-effects on import.

### 16. Redis Connection Pool Is Unbounded Per Instance
**File:** `redis_cache.py` (lines 33–42)

`aioredis.from_url(...)` uses default pool size settings (`max_connections = 50`). Under concurrent request pressure (each request touches Redis at least once for the job store and once for caching), the pool can block or thrash. The in-memory rate-limiter and job store compound this without any back-pressure.

**Fix:** Add `REDIS_MAX_CONNECTIONS` setting (default 20). Pass `max_connections=settings.redis_max_connections` to `from_url`. Also add `socket_connect_timeout=2.0` and `socket_timeout=4.0` so a slow Redis instance does not hold a worker thread indefinitely.

### 17. Cost Score Is Zero by Default for All Free-Classified Cloud Options
**File:** `scoring.py` (lines 56–63)

`_cost_score` returns `1.0` when `cost_per_token == 0`. OpenRouter free-tier models, Groq free tier, and Gemini free API all have `cost_per_token = 0.0` classified. The formula therefore gives them the maximum possible cost bonus, but there is no additional discount applied for them being "less reliable than free" due to API compliance checks.

**Fix:** Decouple `cost_per_token` (financial cost) from `reliability_score` (uptime / compliance score). Add `reliability_weight = 0.15` term in `ScoringWeights`. Reliability is computed as `(consecutive_successes / (max(consecutive_successes + 3, 10)))` with a floor of 0.0 for providers that repeatedly require a tool call for compliance.

### 18. `classifier.py` Fails to Re-Use LM Studio's Warm State
**File:** `classifier.py` (lines 101–133), `routing_helper.py` (lines 69–127)

When routing fails back to Ollama and calibration fails back to heuristics, the system does not cache the result of those failures. If Ollama goes down, every subsequent request pays the 10 s timeout x 9 cloud-classify calls = ~80 s of wasted latency before even reaching the LLM.

**Fix:** Persist the "last good classifier source" per IP/session in Redis with a 5 min TTL. If the preferred classifier failed last time, jump to the next one immediately without retrying the broken one. Maintain a `consecutive_failures` counter and escalate the cooldown duration geometrically (1m → 2m → 4m → 8m → 30m cap).

### 19. `_COMPLEXITY_THRESHOLD` and `_ESCALATION_THRESHOLD` Are Single Values
**File:** `config.py` (lines 90–108), `master_router.py` (lines 217–226)

There is one `LOCAL_COMPLEXITY_THRESHOLD=0.4` for all tasks, regardless of model hardware, session load, or user preference. When the local machine is under load (CPU > 90 %, RAM < 4 GB free), sending even a complexity-0.3 task to local LM Studio will cause LMP or swap-thrashing.

**Fix:** Add `LOCAL_LOAD_CPU_THRESHOLD` (default 85 %) and `LOCAL_LOAD_MEM_THRESHOLD_GB` (default 4 GB) to `Settings`. In `MasterRouter._try_local`, sample `psutil.cpu_percent(0.1)` and `psutil.virtual_memory().available / 1e9` before routing. If peers exceed thresholds, bump the effective local complexity wall upward so cloud precision is preferred even for moderate tasks.

---

## MEDIUM — Quality of Life

### 20. Task Duck-Typing in `router.py` Is Fragile
**File:** `router.py` (line 112–115)

```python
type('TaskRequest', (), {
    'content': enhanced_message,
    'stream': False
})()
```

This is an anonymous object with no Pydantic validation and no type checking. If `TaskRequest` gains a new field, this breaks silently. A structured `TaskRequest` factory method or Pydantic validator in `schemas.py::TaskRequest` must replace this hack.

**Fix:** Add `TaskRequest.simple(content, context=...)` classmethod in `schemas.py` and call it. Remove the anonymous constructor from `router.py`.

### 21. Provider Registry Is Used Directly After Each Classifier Failure
**File:** `master_router.py` (lines 247–254), `router.py` (lines 118–120)

`from app.providers.registry import get_provider_registry()` is called inside the hot loop for every routed request. Moving this to `__init__` removes the repeated import and makes the dependency explicit.

**Fix:** Cache the registry reference in `MasterRouter.__init__`:
```python
from app.providers.registry import get_provider_registry
self._registry = get_provider_registry()
```
Replace all in-loop imports with `self._registry`.

### 22. `routing_helper.py` Reads ENV Directly — Bypasses Config File
**File:** `routing_helper.py` (lines 13–19)

The file reads `LMSTUDIO_BASE_URL = os.getenv(...)` directly instead of using `get_settings()`. This means `LMSTUDIO_BASE_URL` set only in `.env` (which Pydantic loads) will not be picked up here if the `.env` is not the source of truth for the running process. In packaged deployments this can silently return the hardcoded default.

**Fix:** Replace all `os.getenv()` calls in `routing_helper.py` with `get_settings().lmstudio_base_url` etc., removing the direct import-and-use of `dotenv` entirely.

### 23. In-Memory `_job_store` Has No TTL and No Size Cap
**File:** `router.py` (line 38)

```python
_job_store: dict[str, dict[str, Any]] = {}
```

Job results are never evicted. Over days the dict grows without bound. Workers restarted by the OS (signal restart, docker restart) lose all in-flight jobs.

**Fix:** Move the job store to Redis with a TTL of `JOB_TTL_SECONDS = 3600`. Key pattern `job:{job_id}`. On startup, scan an ephemeral queue for dangling jobs and emit a `job_expired` event. For a production deployment with `uvicorn --workers N`, a central Redis store is the only option.

### 24. `LitellmAdapter` Is Imported but Provider Scoring Duplicates Logic
**File:** `providers/litellm_adapter.py` (exists), `providers/optimizer.py`

`litellm_adapter.py` provides cost lookup via LiteLLM's pricing table (`litellm.cost_per_token`). The `optimizer.py` `cost_per_token` field is always `0.0` in practice. This halves the signal the scoring formula is meant to use — cost-awareness is dead code.

**Fix:** Wire `LitellmAdapter` to call `litellm.get_model_info(model_id)` on health-refresh and populate `ProviderBase._cost_per_token` with the real value. Cache the lookup in a `lru_cache`-decorated function. For local models, hardcode `cost_per_token = 0.0`.

### 25. `semantic_cache.py` Index Can Grow Forever Without Cache Eviction
**File:** `semantic_cache.py` (lines 183–186)

The index is capped at 10 000, but TTL is set to `0` (never expires). The existing completions also have `ttl=self._settings.cache_ttl_default` which defaults to 3600 s. When 10 000 embeddings live longer than their indexed TTL every day, deletions from the index do not remove the associated keys in Redis; dead keys accumulate.

**Fix:** After reaching 10 000, evict in LRU order: pop `emb_key` from the front of the index list, then `BATCH_DELETE emb_key AND comp_key`. Use a Lua script in Redis to atomically evict a pair. Set a `cache_max_entries` env var so the cap is configurable per environment.

---

## LOW — Polish

### 26. `get_settings()` Is `@lru_cache(maxsize=1)` — No Hot-Reload
**File:** `config.py` (line 187)

Settings are resolved once at import time and never reloaded. Changing any env var or `.env` requires a full process restart.

**Fix:** Add a `settings_reload()` function that clears the LRU cache. Hook it to the `SIGHUP` signal handler and to the `/api/v1/admin/reload-config` endpoint (behind admin JWT).

### 27. Prometheus Metrics Never Reset
**Files:** `observability/metrics.py` (implied from imports)

`provider_requests_total`, `cache_hits_total`, etc., are defined as monotonically-increasing `Counter` objects. On a 30 day deployment, cardinality on `provider_id`, `model_id`, and `status` labels grows without limit.

**Fix:** Wire a periodic job (hourly) that samples counter values and resets to zero when the browser-scrape window returns. Document this in Grafana dashboards with `rate(...[5m])` queries so resets produce no spike artefact.

### 28. Classifier `compress_context` Drops Messages Without Warning
**File:** `classifier.py` (lines 657–676)

When context exceeds the token limit the classifier drops the oldest messages. No log entry, no alert, no user-facing warning. The user's last 50 messages can vanish into the trash without trace.

**Fix:** Log a `context_compression` event with the count of dropped messages at `WARNING` level. If dropped message count > 20, add a system-message placeholder: `"(Earlier context was summarised. Relevant details may have been lost.)"`.

---

## Summary Table

| #   | File(s) Affected                           | Severity  | Risk if Ignored                                  |
|-----|--------------------------------------------|-----------|-------------------------------------------------|
| 1   | `config.py`, `optimizer.py`, `scoring.py` | CRITICAL  | Budget overrun; no real quota enforcement        |
| 2   | `master_router.py`                         | CRITICAL  | System routes to paid providers by default       |
| 3   | `classifier.py`                            | CRITICAL  | 900+ ext. API calls/100 req burst, rate limits   |
| 4   | `semantic_cache.py`                        | CRITICAL  | Cache causes O(n) OOM at any scale               |
| 5   | `lmstudio_provider.py`, `ollama_provider.py`| CRITICAL  | Load-balancer routes to dead/broken providers    |
| 6   | `middleware.py`                            | HIGH      | Rate limiter bypassed on WS / local path          |
| 7   | `optimizer.py`                             | HIGH      | No monthly budget; counters lost on restart       |
| 8   | `memory/manager.py`                        | HIGH      | Redis & Qdrant grow unbounded                     |
| 9   | `lmstudio_provider.py`, `.env`             | HIGH      | GPU not configured; local inference throttled     |
| 10  | `middleware.py`                            | HIGH      | Rate limit broken on multi-worker deployment     |
| 11  | `optimizer.py`, all providers              | HIGH      | Silent quota drain without 429 detection          |
| 12  | `router.py`                                | HIGH      | Unhelpful errors on total provider exhaustion     |
| 13  | `classifier.py`                            | HIGH      | Latency spikes to 80 s on first failure            |
| 14  | `requirements.txt`, `semantic_cache.py`    | HIGH      | Heavy install; crashes without GPU                |
| 15  | `routing_helper.py`                        | HIGH      | Silent misconfiguration without dotenv            |
| 16  | `redis_cache.py`                           | MEDIUM    | Redis pool exhaustion under load                  |
| 17  | `scoring.py`                               | MEDIUM    | Scoring weakened by always-zero cost field        |
| 18  | `classifier.py`, `routing_helper.py`       | MEDIUM    | No cooldown backoff on repeated classifier failure |
| 19  | `config.py`, `master_router.py`            | MEDIUM    | Local model overloaded when system is under load   |
| 20  | `router.py`                                | MEDIUM    | Fragile TaskRequest instantiation                 |
| 21  | `master_router.py`                         | MEDIUM    | Registry re-imported in hot loop                  |
| 22  | `routing_helper.py`                        | MEDIUM    | Config bypassed; env vars not centrally managed    |
| 23  | `router.py`                                | MEDIUM    | In-memory job store grows forever                 |
| 24  | `optimizer.py`, `litellm_adapter.py`       | MEDIUM    | Cost signal is dead code                          |
| 25  | `semantic_cache.py`                        | MEDIUM    | Dead keys accumulate in Redis index               |
| 26  | `config.py`                                | LOW       | No hot-reload; restart required for config change |
| 27  | `observability/metrics.py`                 | LOW       | Prometheus counters leak cardinality over time     |
| 28  | `classifier.py`                            | LOW       | Silent context truncation on long threads          |
