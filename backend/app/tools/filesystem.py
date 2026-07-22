"""
Filesystem MCP tool.
Sandboxed to the configured working directory.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import aiofiles

from app.observability.logging_config import get_logger
from app.tools.base import MCPTool, ToolResult

logger = get_logger(__name__)

_DEFAULT_SANDBOX = Path("./workspace").resolve()


class FilesystemTool(MCPTool):
    """
    Provides sandboxed filesystem operations:
    read_file, write_file, list_directory, search_files
    """

    tool_id = "filesystem"
    category = "filesystem"
    description = "Read, write, list, and search files within the sandbox directory"

    def __init__(self, sandbox_dir: Path = _DEFAULT_SANDBOX) -> None:
        self._sandbox = sandbox_dir.resolve()
        self._sandbox.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, relative_path: str) -> Path:
        """
        Resolve a relative path within the sandbox.
        Raises PermissionError if the resolved path escapes the sandbox.
        """
        resolved = (self._sandbox / relative_path).resolve()
        if not str(resolved).startswith(str(self._sandbox)):
            raise PermissionError(
                f"Path traversal attempt blocked: '{relative_path}' resolves outside sandbox"
            )
        return resolved

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """
        Execute a filesystem operation.
        params must include 'operation' key.
        """
        operation = params.get("operation", "")
        start = time.perf_counter()

        try:
            if operation == "read_file":
                return await self._read_file(params, start)
            elif operation == "write_file":
                return await self._write_file(params, start)
            elif operation == "list_directory":
                return await self._list_directory(params, start)
            elif operation == "search_files":
                return await self._search_files(params, start)
            else:
                return self._timed_result(
                    None, start, exit_status=1, error=f"Unknown operation: '{operation}'"
                )
        except PermissionError as exc:
            logger.warning("filesystem_permission_error", operation=operation, error=str(exc))
            return self._timed_result(None, start, exit_status=1, error=str(exc))
        except Exception as exc:
            logger.error("filesystem_error", operation=operation, error=str(exc))
            return self._timed_result(None, start, exit_status=1, error=str(exc))

    async def _read_file(self, params: dict, start: float) -> ToolResult:
        path = self._safe_path(params["path"])
        if not path.exists():
            return self._timed_result(None, start, exit_status=1, error=f"File not found: {params['path']}")
        async with aiofiles.open(path, "r", encoding="utf-8", errors="replace") as f:
            content = await f.read()
        return self._timed_result(content, start)

    async def _write_file(self, params: dict, start: float) -> ToolResult:
        path = self._safe_path(params["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        content = params.get("content", "")
        mode = params.get("mode", "w")  # "w" or "a"
        async with aiofiles.open(path, mode, encoding="utf-8") as f:
            await f.write(content)
        return self._timed_result({"written": len(content), "path": str(path)}, start)

    async def _list_directory(self, params: dict, start: float) -> ToolResult:
        path = self._safe_path(params.get("path", "."))
        if not path.is_dir():
            return self._timed_result(None, start, exit_status=1, error=f"Not a directory: {params.get('path')}")
        entries = []
        for entry in sorted(path.iterdir()):
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
        return self._timed_result(entries, start)

    async def _search_files(self, params: dict, start: float) -> ToolResult:
        pattern = params.get("pattern", "*")
        search_dir = self._safe_path(params.get("path", "."))
        recursive = params.get("recursive", True)

        if recursive:
            matches = list(search_dir.rglob(pattern))
        else:
            matches = list(search_dir.glob(pattern))

        # Filter to files only and limit results
        results = [
            str(m.relative_to(self._sandbox))
            for m in matches[:100]
            if m.is_file()
        ]
        return self._timed_result(results, start)
