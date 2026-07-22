"""
Qdrant vector store for embedding-based memory retrieval.
"""
from __future__ import annotations

from typing import Optional
from uuid import uuid4

from app.config import get_settings
from app.observability.logging_config import get_logger

logger = get_logger(__name__)

_COLLECTION_NAME = "haios_memory"
_VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimension


class VectorStore:
    """
    Qdrant-backed vector store for semantic memory retrieval.
    Lazily initializes the Qdrant client and collection.
    """

    def __init__(self) -> None:
        self._client: Optional[object] = None
        self._encoder: Optional[object] = None
        self._initialized = False

    async def _ensure_initialized(self) -> bool:
        """Initialize Qdrant client and collection. Returns False if unavailable."""
        if self._initialized:
            return self._client is not None

        settings = get_settings()
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import Distance, VectorParams

            kwargs: dict = {"url": settings.qdrant_url}
            if settings.qdrant_api_key:
                kwargs["api_key"] = settings.qdrant_api_key

            self._client = AsyncQdrantClient(**kwargs)

            # Create collection if it doesn't exist
            collections = await self._client.get_collections()  # type: ignore[attr-defined]
            existing = [c.name for c in collections.collections]
            if _COLLECTION_NAME not in existing:
                await self._client.create_collection(  # type: ignore[attr-defined]
                    collection_name=_COLLECTION_NAME,
                    vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info("qdrant_collection_created", collection=_COLLECTION_NAME)

            self._initialized = True
            logger.info("qdrant_initialized", url=settings.qdrant_url)
            return True

        except Exception as exc:
            logger.warning("qdrant_unavailable", error=str(exc))
            self._client = None
            self._initialized = True  # Mark as attempted to avoid repeated retries
            return False

    def _get_encoder(self) -> Optional[object]:
        """Lazily load the sentence-transformers encoder."""
        if self._encoder is not None:
            return self._encoder
        try:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as exc:
            logger.warning("encoder_unavailable", error=str(exc))
        return self._encoder

    def _embed(self, text: str) -> Optional[list[float]]:
        """Generate an embedding vector for the given text."""
        encoder = self._get_encoder()
        if encoder is None:
            return None
        try:
            vec = encoder.encode(text, normalize_embeddings=True)  # type: ignore[attr-defined]
            return vec.tolist()
        except Exception as exc:
            logger.warning("embedding_error", error=str(exc))
            return None

    async def upsert(
        self,
        text: str,
        metadata: dict,
        point_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Store a text embedding in Qdrant.
        Returns the point ID on success, None on failure.
        """
        available = await self._ensure_initialized()
        if not available or self._client is None:
            return None

        embedding = self._embed(text)
        if embedding is None:
            return None

        pid = point_id or str(uuid4())
        try:
            from qdrant_client.models import PointStruct

            await self._client.upsert(  # type: ignore[attr-defined]
                collection_name=_COLLECTION_NAME,
                points=[PointStruct(id=pid, vector=embedding, payload={"text": text, **metadata})],
            )
            logger.debug("vector_upserted", point_id=pid)
            return pid
        except Exception as exc:
            logger.warning("vector_upsert_error", error=str(exc))
            return None

    async def search(
        self,
        query: str,
        k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        """
        Search for the top-K most similar vectors to the query.
        Returns a list of payload dicts with similarity scores.
        """
        available = await self._ensure_initialized()
        if not available or self._client is None:
            return []

        embedding = self._embed(query)
        if embedding is None:
            return []

        try:
            results = await self._client.search(  # type: ignore[attr-defined]
                collection_name=_COLLECTION_NAME,
                query_vector=embedding,
                limit=k,
                score_threshold=score_threshold,
            )
            return [
                {"score": r.score, "text": r.payload.get("text", ""), **r.payload}
                for r in results
            ]
        except Exception as exc:
            logger.warning("vector_search_error", error=str(exc))
            return []

    async def ensure_collection_exists(self) -> bool:
        """Ensure the Qdrant collection exists. Returns True if available."""
        return await self._ensure_initialized()

    async def delete(self, point_id: str) -> None:
        """Delete a point from the vector store."""
        available = await self._ensure_initialized()
        if not available or self._client is None:
            return
        try:
            from qdrant_client.models import PointIdsList

            await self._client.delete(  # type: ignore[attr-defined]
                collection_name=_COLLECTION_NAME,
                points_selector=PointIdsList(points=[point_id]),
            )
        except Exception as exc:
            logger.warning("vector_delete_error", error=str(exc))


_vector_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the singleton VectorStore instance."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
