"""
Memory system coordinator.
Orchestrates episodic, semantic, and vector memory tiers.
"""
from __future__ import annotations

from typing import Optional

from app.config import get_settings
from app.memory.episodic import EpisodicMemory
from app.memory.semantic import SemanticMemory
from app.memory.vector_store import VectorStore, get_vector_store
from app.observability.logging_config import get_logger
from app.observability.metrics import memory_retrievals_total

logger = get_logger(__name__)


class MemoryManager:
    """
    Coordinates all memory tiers:
    - Episodic: per-session conversation history (Redis)
    - Semantic: long-term factual knowledge (SQLite/PostgreSQL)
    - Vector: embedding-indexed knowledge (Qdrant)
    """

    def __init__(self) -> None:
        self._episodic = EpisodicMemory()
        self._semantic = SemanticMemory()
        self._vector: VectorStore = get_vector_store()
        self._settings = get_settings()

    # ─── Episodic Memory ───────────────────────────────────────────────

    async def store_episodic(self, session_id: str, role: str, content: str) -> None:
        """Store a message in episodic memory for the given session."""
        await self._episodic.store(session_id, role, content)

        # Auto-compress if over token limit
        count = await self._episodic.count(session_id)
        # Rough estimate: each message ≈ 50 tokens
        if count * 50 > self._settings.episodic_token_limit:
            await self.summarize_session(session_id)

    async def get_episodic(self, session_id: str, limit: int = 50) -> list[dict]:
        """Retrieve recent episodic memory for a session."""
        memory_retrievals_total.labels(memory_type="episodic").inc()
        return await self._episodic.get(session_id, limit=limit)

    # ─── Semantic Memory ───────────────────────────────────────────────

    async def store_semantic(
        self,
        fact: str,
        source: str,
        confidence: float,
        session_id: Optional[str] = None,
    ) -> str:
        """Store a fact in semantic memory and index it in the vector store."""
        fact_id = await self._semantic.store(fact, source, confidence, session_id)

        # Also index in vector store for similarity retrieval
        await self._vector.upsert(
            text=fact,
            metadata={"fact_id": fact_id, "source": source, "confidence": confidence},
            point_id=fact_id,
        )
        return fact_id

    # ─── Vector Memory ─────────────────────────────────────────────────

    async def retrieve_relevant(self, query: str, k: Optional[int] = None) -> list[dict]:
        """
        Retrieve the top-K most semantically relevant memories for a query.
        Returns an empty list if no results above the similarity threshold.
        """
        top_k = k or self._settings.memory_top_k
        memory_retrievals_total.labels(memory_type="vector").inc()
        results = await self._vector.search(query, k=top_k, score_threshold=0.5)
        logger.debug("memory_retrieved", query_length=len(query), results=len(results))
        return results

    # ─── Session Lifecycle ─────────────────────────────────────────────

    async def summarize_session(self, session_id: str) -> Optional[str]:
        """
        Compress episodic memory for a session by summarizing older entries.
        Retains the summary in place of the full history.
        """
        messages = await self._episodic.get_all(session_id)
        if len(messages) < 10:
            return None

        # Keep the last 10 messages; summarize the rest
        to_summarize = messages[:-10]
        recent = messages[-10:]

        # Build a simple summary (in production, use LLM summarization)
        summary_text = f"[Summary of {len(to_summarize)} earlier messages: "
        summary_text += "; ".join(
            f"{m['role']}: {m['content'][:50]}" for m in to_summarize[:5]
        )
        summary_text += "...]"

        # Clear and rewrite with summary + recent
        await self._episodic.clear(session_id)
        await self._episodic.store(session_id, "system", summary_text)
        for msg in recent:
            await self._episodic.store(session_id, msg["role"], msg["content"])

        logger.info(
            "session_summarized",
            session_id=session_id,
            original_count=len(messages),
            retained_count=len(recent) + 1,
        )
        return summary_text

    async def on_session_end(self, session_id: str) -> None:
        """
        Called when a session ends normally.
        Summarizes and persists the session to semantic memory.
        """
        messages = await self._episodic.get_all(session_id)
        if not messages:
            return

        summary = f"Session {session_id}: {len(messages)} messages exchanged."
        await self.store_semantic(
            fact=summary,
            source=f"session:{session_id}",
            confidence=0.9,
            session_id=session_id,
        )
        logger.info("session_ended_persisted", session_id=session_id)

    async def on_session_crash(self, session_id: str) -> None:
        """
        Called when a session ends abruptly.
        Logs the incomplete session without requiring a summary.
        """
        count = await self._episodic.count(session_id)
        logger.warning(
            "session_crashed_incomplete",
            session_id=session_id,
            message_count=count,
        )


_memory_manager_instance: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Return the singleton MemoryManager instance."""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = MemoryManager()
    return _memory_manager_instance
