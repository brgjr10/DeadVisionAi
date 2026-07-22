"""
Tool registry — manages all registered MCP tools.
"""
from __future__ import annotations

from typing import Optional

from app.observability.logging_config import get_logger
from app.observability.metrics import tool_duration_seconds, tool_executions_total
from app.routing.schemas import TaskClassification
from app.tools.base import MCPTool, ToolResult

logger = get_logger(__name__)


class ToolRegistry:
    """
    Registry for MCP tools.
    Supports registration, lookup, and execution with metrics tracking.
    """

    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}

    def register(self, tool: MCPTool) -> None:
        """Register a tool. Overwrites any existing tool with the same ID."""
        self._tools[tool.tool_id] = tool
        logger.info("tool_registered", tool_id=tool.tool_id, category=tool.category)

    def get_tools_for_task(self, classification: TaskClassification) -> list[MCPTool]:
        """
        Return tools recommended for the given task classification.
        Filters by recommended_tools list and tool_only_flag.
        """
        if not classification.recommended_tools:
            return []
        return [
            self._tools[tid]
            for tid in classification.recommended_tools
            if tid in self._tools
        ]

    async def execute_tool(self, tool_id: str, params: dict) -> ToolResult:
        """
        Execute a tool by ID with the given parameters.
        Records execution metrics and handles errors gracefully.
        """
        tool = self._tools.get(tool_id)
        if tool is None:
            logger.error("tool_not_found", tool_id=tool_id)
            return ToolResult(
                result=None,
                duration_ms=0.0,
                exit_status=1,
                error=f"Tool '{tool_id}' not found in registry",
            )

        try:
            result = await tool.execute(params)
            status = "success" if result.success else "failure"
            tool_executions_total.labels(tool_id=tool_id, status=status).inc()
            tool_duration_seconds.labels(tool_id=tool_id).observe(result.duration_ms / 1000)
            logger.info(
                "tool_executed",
                tool_id=tool_id,
                status=status,
                duration_ms=result.duration_ms,
            )
            return result
        except Exception as exc:
            logger.error("tool_execution_error", tool_id=tool_id, error=str(exc))
            tool_executions_total.labels(tool_id=tool_id, status="error").inc()
            return ToolResult(
                result=None,
                duration_ms=0.0,
                exit_status=1,
                error=str(exc),
            )

    def list_tools(self) -> list[dict]:
        """Return a list of all registered tools."""
        return [
            {"tool_id": t.tool_id, "category": t.category, "description": t.description}
            for t in self._tools.values()
        ]


_tool_registry_instance: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Return the singleton ToolRegistry instance."""
    global _tool_registry_instance
    if _tool_registry_instance is None:
        _tool_registry_instance = ToolRegistry()
    return _tool_registry_instance
