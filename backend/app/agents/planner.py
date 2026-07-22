"""
Planner agent — decomposes complex tasks into subtasks.
"""
from __future__ import annotations

from app.agents.base import AgentBase, AgentRole, TaskObject, TaskStatus
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class PlannerAgent(AgentBase):
    """
    Decomposes multi-step tasks into ordered or parallelizable subtasks.
    """

    role = AgentRole.PLANNER
    description = "Decomposes complex tasks into structured subtask plans"

    async def execute(self, task: TaskObject) -> TaskObject:
        """
        Analyze the task input and produce a decomposition plan.
        The plan is stored in task.output as a list of subtask descriptions.
        """
        try:
            task.status = TaskStatus.IN_PROGRESS
            input_text = str(task.input or "")

            # Simple heuristic decomposition (replace with LLM in production)
            steps = self._decompose(input_text)
            task.output = {"steps": steps, "parallel": False}
            task.status = TaskStatus.COMPLETED
            logger.info(
                "planner_completed",
                task_id=task.task_id,
                steps=len(steps),
            )
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            logger.error("planner_failed", task_id=task.task_id, error=str(exc))
        return task

    def _decompose(self, text: str) -> list[str]:
        """Simple sentence-based decomposition."""
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if len(sentences) <= 1:
            return [text]
        return sentences[:10]  # cap at 10 steps
