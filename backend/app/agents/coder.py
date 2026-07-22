"""
Coder agent — handles code generation and modification tasks.
"""
from __future__ import annotations

from app.agents.base import AgentBase, AgentRole, TaskObject, TaskStatus
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class CoderAgent(AgentBase):
    """
    Generates, reviews, and modifies code.
    Routes to the best available code-capable model.
    """

    role = AgentRole.CODER
    description = "Generates and modifies code using the best available model"

    async def execute(self, task: TaskObject) -> TaskObject:
        """Execute a code generation or modification task."""
        try:
            task.status = TaskStatus.IN_PROGRESS
            # In production: route to code-capable model via MasterRouter
            # For Phase 1: placeholder that marks task for LLM routing
            task.output = {
                "type": "code_task",
                "input": task.input,
                "requires_llm": True,
                "preferred_model": "code-capable",
            }
            task.status = TaskStatus.COMPLETED
            logger.info("coder_task_prepared", task_id=task.task_id)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            logger.error("coder_failed", task_id=task.task_id, error=str(exc))
        return task
