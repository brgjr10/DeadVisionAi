"""
Semantic similarity cache.
Matches new prompts to stored prompts using embedding cosine similarity.
Returns cached completions when similarity exceeds the configured threshold.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Optional

import numpy as np

from app.cache.redis_cache import get_redis_cache
from app.config import get_settings
from app.observability.logging_config import get_logger
from app.observability.metrics import cache_hits_total, cache_misses_total

logger = get_logger(__name__)

_CACHE_TYPE = "semantic"
_EMBEDDING_KEY_PREFIX = "sem_emb:"
_COMPLETION_KEY_PREFIX = "sem_comp:"
_INDEX_KEY = "sem_index"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


class SemanticCache:
    """
    Semantic cache backed by Redis.
    Uses sentence-transformers for local embeddings (falls back to hash-based exact match).
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._encoder: Optional[object] = None
        self._encoder_loaded = False

    def _load_encoder(self) -> Optional[object]:
        """Lazily load the sentence-transformers encoder."""
        if self._encoder_loaded:
            return self._encoder
        try:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("sentence_transformer_loaded", model="all-MiniLM-L6-v2")
        except Exception as exc:
            logger.warning("sentence_transformer_unavailable", error=str(exc))
            self._encoder = None
        self._encoder_loaded = True
        return self._encoder

    def _embed(self, text: str) -> Optional[list[float]]:
        """Generate an embedding for the given text."""
        encoder = self._load_encoder()
        if encoder is None:
            return None
        try:
            embedding = encoder.encode(text, normalize_embeddings=True)  # type: ignore[attr-defined]
            return embedding.tolist()
        except Exception as exc:
            logger.warning("embedding_failed", error=str(exc))
            return None

    def _prompt_hash(self, prompt: str) -> str:
        """Return a short hash of the prompt for use as a cache key."""
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    async def lookup(self, prompt: str) -> Optional[str]:
        """
        Look up a cached completion for the given prompt.
        Returns the cached completion if similarity >= threshold, else None.
        """
        cache = get_redis_cache()
        threshold = self._settings.semantic_cache_threshold

        # First try exact match (fast path)
        exact_key = f"{_COMPLETION_KEY_PREFIX}exact:{self._prompt_hash(prompt)}"
        exact_result = await cache.get(exact_key)
        if exact_result:
            cache_hits_total.labels(cache_type="exact").inc()
            logger.debug("semantic_cache_exact_hit")
            return exact_result

        # Semantic similarity search
        query_embedding = self._embed(prompt)
        if query_embedding is None:
            cache_misses_total.labels(cache_type=_CACHE_TYPE).inc()
            return None

        # Load the index of stored embedding keys
        index_raw = await cache.get(_INDEX_KEY)
        if not index_raw:
            cache_misses_total.labels(cache_type=_CACHE_TYPE).inc()
            return None

        try:
            index: list[str] = json.loads(index_raw)
        except Exception:
            cache_misses_total.labels(cache_type=_CACHE_TYPE).inc()
            return None

        best_similarity = 0.0
        best_key: Optional[str] = None

        for emb_key in index:
            emb_raw = await cache.get(emb_key)
            if not emb_raw:
                continue
            try:
                stored_embedding: list[float] = json.loads(emb_raw)
                sim = _cosine_similarity(query_embedding, stored_embedding)
                if sim > best_similarity:
                    best_similarity = sim
                    best_key = emb_key
            except Exception:
                continue

        if best_similarity >= threshold and best_key:
            # Retrieve the corresponding completion
            comp_key = best_key.replace(_EMBEDDING_KEY_PREFIX, _COMPLETION_KEY_PREFIX)
            completion = await cache.get(comp_key)
            if completion:
                cache_hits_total.labels(cache_type=_CACHE_TYPE).inc()
                logger.debug(
                    "semantic_cache_hit",
                    similarity=round(best_similarity, 4),
                    threshold=threshold,
                )
                return completion

        cache_misses_total.labels(cache_type=_CACHE_TYPE).inc()
        logger.debug(
            "semantic_cache_miss",
            best_similarity=round(best_similarity, 4),
            threshold=threshold,
        )
        return None

    async def store(self, prompt: str, completion: str, ttl: int = 0) -> None:
        """
        Store a prompt-completion pair in the semantic cache.
        Also stores the embedding for future similarity lookups.
        """
        cache = get_redis_cache()
        if ttl == 0:
            ttl = self._settings.cache_ttl_default

        prompt_hash = self._prompt_hash(prompt)

        # Store exact match
        exact_key = f"{_COMPLETION_KEY_PREFIX}exact:{prompt_hash}"
        await cache.set(exact_key, completion, ttl)

        # Store embedding for semantic search
        embedding = self._embed(prompt)
        if embedding is None:
            return

        emb_key = f"{_EMBEDDING_KEY_PREFIX}{prompt_hash}"
        comp_key = f"{_COMPLETION_KEY_PREFIX}{prompt_hash}"

        await cache.set(emb_key, json.dumps(embedding), ttl)
        await cache.set(comp_key, completion, ttl)

        # Update the index
        index_raw = await cache.get(_INDEX_KEY)
        index: list[str] = json.loads(index_raw) if index_raw else []
        if emb_key not in index:
            index.append(emb_key)
            # Keep index bounded
            if len(index) > 10000:
                index = index[-10000:]
            await cache.set(_INDEX_KEY, json.dumps(index), ttl=0)

        logger.debug("semantic_cache_stored", prompt_hash=prompt_hash)


_semantic_cache_instance: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    """Return the singleton SemanticCache instance."""
    global _semantic_cache_instance
    if _semantic_cache_instance is None:
        _semantic_cache_instance = SemanticCache()
    return _semantic_cache_instance
