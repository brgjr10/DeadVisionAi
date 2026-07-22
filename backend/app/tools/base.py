"""
Abstract MCP tool interface.
All tools must implement this interface.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    """Structured result from a tool execution."""

    result: Any
    duration_ms: float
    exit_status: int = 0  # 0 = success
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.exit_status == 0 and self.error is None


class MCPTool(ABC):
    """
    Abstract base class for all MCP tools.
    Tools are sandboxed, structured, and return ToolResult objects.
    """

    tool_id: str
    category: str
    description: str = ""

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """
        Execute the tool with the given parameters.
        Must return a ToolResult — never raise unhandled exceptions.
        """
        ...

    def _timed_result(
        self,
        result: Any,
        start_time: float,
        exit_status: int = 0,
        error: Optional[str] = None,
    ) -> ToolResult:
        """Helper to build a ToolResult with elapsed time."""
        duration_ms = (time.perf_counter() - start_time) * 1000
        return ToolResult(
            result=result,
            duration_ms=round(duration_ms, 2),
            exit_status=exit_status,
            error=error,
        )
