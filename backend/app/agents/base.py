"""
Abstract agent interface.
All specialized agents implement this base class.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class AgentRole(str, Enum):
    PLANNER = "planner"
    CODER = "coder"
    RESEARCHER = "researcher"
    VERIFIER = "verifier"
    SUMMARIZER = "summarizer"
    MEMORY_MANAGER = "memory_manager"
    TOOL_SPECIALIST = "tool_specialist"
    DEBUGGING_AGENT = "debugging_agent"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    UNVERIFIED = "unverified"


@dataclass
class TaskObject:
    """
    Structured unit of work passed between agents.
    All agent communication uses TaskObjects exclusively.
    """

    task_id: str = field(default_factory=lambda: str(uuid4()))
    task_type: str = ""
    input: Any = None
    output: Any = None
    status: TaskStatus = TaskStatus.PENDING
    error: Optional[str] = None
    assigned_role: Optional[AgentRole] = None
    session_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    parent_task_id: Optional[str] = None
    depth: int = 0


class AgentBase(ABC):
    """
    Abstract base class for all HAIOS agents.
    """

    role: AgentRole
    description: str = ""

    @abstractmethod
    async def execute(self, task: TaskObject) -> TaskObject:
        """
        Execute the given task and return the updated TaskObject.
        Must set task.status to COMPLETED or FAILED.
        Must never raise unhandled exceptions.
        """
        ...

    @property
    def agent_id(self) -> str:
        return self.role.value
