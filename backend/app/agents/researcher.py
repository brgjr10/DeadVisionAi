"""
Researcher agent — gathers information via web search and memory retrieval.
"""
from __future__ import annotations

from app.agents.base import AgentBase, AgentRole, TaskObject, TaskStatus
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class ResearcherAgent(AgentBase):
    """
    Gathers information using web search tools and memory retrieval.
    """

    role = AgentRole.RESEARCHER
    description = "Gathers information via web search and memory retrieval"

    async def execute(self, task: TaskObject) -> TaskObject:
        """Execute a research task."""
        try:
            task.status = TaskStatus.IN_PROGRESS
            query = str(task.input or "")

            # Retrieve from memory first
            from app.memory.manager import get_memory_manager

            memory_manager = get_memory_manager()
            relevant_memories = await memory_manager.retrieve_relevant(query, k=3)

            # Execute web search
            from app.tools.registry import get_tool_registry

            registry = get_tool_registry()
            search_result = await registry.execute_tool(
                "web_search", {"query": query, "max_results": 5}
            )

            task.output = {
                "memories": relevant_memories,
                "web_results": search_result.result if search_result.success else [],
                "query": query,
            }
            task.status = TaskStatus.COMPLETED
            logger.info("researcher_completed", task_id=task.task_id)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            logger.error("researcher_failed", task_id=task.task_id, error=str(exc))
        return task
