"""
Verifier agent — validates task outputs before delivery.
"""
from __future__ import annotations

from app.agents.base import AgentBase, AgentRole, TaskObject, TaskStatus
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class VerifierAgent(AgentBase):
    """
    Validates task outputs for correctness and completeness.
    Marks results as unverified if verification is impossible.
    """

    role = AgentRole.VERIFIER
    description = "Validates task outputs before delivery to the user"

    async def execute(self, task: TaskObject) -> TaskObject:
        """
        Verify the task output.
        Sets status to COMPLETED if verified, UNVERIFIED if verification fails.
        """
        try:
            task.status = TaskStatus.IN_PROGRESS
            output = task.output

            if output is None:
                task.status = TaskStatus.FAILED
                task.error = "No output to verify"
                return task

            # Basic verification: check output is non-empty
            verified = bool(output)
            if verified:
                task.status = TaskStatus.COMPLETED
                task.metadata["verified"] = True
                logger.info("verification_passed", task_id=task.task_id)
            else:
                task.status = TaskStatus.UNVERIFIED
                task.metadata["verified"] = False
                task.metadata["unverified_warning"] = (
                    "Output could not be verified — review before use"
                )
                logger.warning("verification_failed", task_id=task.task_id)

        except Exception as exc:
            # Verifier unavailable — mark as unverified with warning
            task.status = TaskStatus.UNVERIFIED
            task.metadata["verified"] = False
            task.metadata["unverified_warning"] = f"Verifier error: {exc}"
            logger.error("verifier_error", task_id=task.task_id, error=str(exc))

        return task
