"""
Semantic memory — long-term factual knowledge store.
Backed by SQLite/PostgreSQL for structured storage.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.observability.logging_config import get_logger

logger = get_logger(__name__)

# In-memory fallback store (replace with SQLAlchemy in production)
_semantic_store: list[dict] = []


class SemanticMemory:
    """
    Stores and retrieves long-term factual knowledge.
    Each fact has a source reference and confidence score.
    """

    async def store(
        self,
        fact: str,
        source: str,
        confidence: float,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Store a new fact in semantic memory.
        Returns the fact ID.
        """
        fact_id = str(uuid4())
        entry = {
            "id": fact_id,
            "fact": fact,
            "source": source,
            "confidence": confidence,
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _semantic_store.append(entry)
        logger.debug(
            "semantic_fact_stored",
            fact_id=fact_id,
            source=source,
            confidence=confidence,
        )
        return fact_id

    async def retrieve_all(self, min_confidence: float = 0.0) -> list[dict]:
        """Retrieve all facts above the minimum confidence threshold."""
        return [f for f in _semantic_store if f["confidence"] >= min_confidence]

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """
        Simple keyword search over stored facts.
        In production, this is replaced by vector similarity search.
        """
        query_lower = query.lower()
        results = [
            f for f in _semantic_store
            if query_lower in f["fact"].lower()
        ]
        return results[:limit]

    async def delete(self, fact_id: str) -> None:
        """Delete a fact by ID."""
        global _semantic_store
        _semantic_store = [f for f in _semantic_store if f["id"] != fact_id]
        logger.debug("semantic_fact_deleted", fact_id=fact_id)


_semantic_instance: Optional[SemanticMemory] = None


def get_semantic_memory() -> SemanticMemory:
    """Return the singleton SemanticMemory instance."""
    global _semantic_instance
    if _semantic_instance is None:
        _semantic_instance = SemanticMemory()
    return _semantic_instance
