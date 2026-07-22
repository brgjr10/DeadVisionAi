"""
Git MCP tool.
Provides sandboxed git operations within the workspace directory.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from app.observability.logging_config import get_logger
from app.tools.base import MCPTool, ToolResult

logger = get_logger(__name__)

_DEFAULT_SANDBOX = Path("./workspace").resolve()
_GIT_TIMEOUT = 60  # seconds


class GitTool(MCPTool):
    """
    Provides git operations: clone, status, diff, log, commit.
    All operations are sandboxed to the workspace directory.
    """

    tool_id = "git"
    category = "git"
    description = "Git operations (clone, status, diff, log, commit) within the workspace"

    def __init__(self, sandbox_dir: Path = _DEFAULT_SANDBOX) -> None:
        self._sandbox = sandbox_dir.resolve()
        self._sandbox.mkdir(parents=True, exist_ok=True)

    async def _run_git(self, args: list[str], cwd: Path) -> tuple[str, str, int]:
        """Run a git command and return (stdout, stderr, exit_code)."""
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=_GIT_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return "", "Git command timed out", 124

        return (
            stdout_b.decode("utf-8", errors="replace"),
            stderr_b.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """
        Execute a git operation.
        params:
            operation: str — one of: clone, status, diff, log, commit, pull
            repo_url: str — for clone
            path: str — relative path within sandbox (default ".")
            message: str — for commit
            args: list[str] — additional git args
        """
        operation = params.get("operation", "").strip()
        start = time.perf_counter()

        try:
            if operation == "clone":
                return await self._clone(params, start)
            elif operation == "status":
                return await self._status(params, start)
            elif operation == "diff":
                return await self._diff(params, start)
            elif operation == "log":
                return await self._log(params, start)
            elif operation == "commit":
                return await self._commit(params, start)
            elif operation == "pull":
                return await self._pull(params, start)
            else:
                return self._timed_result(
                    None, start, exit_status=1, error=f"Unknown git operation: '{operation}'"
                )
        except Exception as exc:
            logger.error("git_tool_error", operation=operation, error=str(exc))
            return self._timed_result(None, start, exit_status=1, error=str(exc))

    async def _clone(self, params: dict, start: float) -> ToolResult:
        repo_url = params.get("repo_url", "")
        dest = params.get("path", "repo")
        dest_path = (self._sandbox / dest).resolve()
        if not str(dest_path).startswith(str(self._sandbox)):
            return self._timed_result(None, start, exit_status=1, error="Path traversal blocked")
        stdout, stderr, code = await self._run_git(["clone", repo_url, str(dest_path)], self._sandbox)
        return self._timed_result({"stdout": stdout, "stderr": stderr}, start, exit_status=code)

    async def _status(self, params: dict, start: float) -> ToolResult:
        path = (self._sandbox / params.get("path", ".")).resolve()
        stdout, stderr, code = await self._run_git(["status", "--short"], path)
        return self._timed_result({"stdout": stdout, "stderr": stderr}, start, exit_status=code)

    async def _diff(self, params: dict, start: float) -> ToolResult:
        path = (self._sandbox / params.get("path", ".")).resolve()
        extra = params.get("args", [])
        stdout, stderr, code = await self._run_git(["diff"] + extra, path)
        return self._timed_result({"stdout": stdout, "stderr": stderr}, start, exit_status=code)

    async def _log(self, params: dict, start: float) -> ToolResult:
        path = (self._sandbox / params.get("path", ".")).resolve()
        limit = params.get("limit", 10)
        stdout, stderr, code = await self._run_git(
            ["log", f"--max-count={limit}", "--oneline"], path
        )
        return self._timed_result({"stdout": stdout, "stderr": stderr}, start, exit_status=code)

    async def _commit(self, params: dict, start: float) -> ToolResult:
        path = (self._sandbox / params.get("path", ".")).resolve()
        message = params.get("message", "Auto-commit by HAIOS")
        # Stage all changes
        await self._run_git(["add", "-A"], path)
        stdout, stderr, code = await self._run_git(["commit", "-m", message], path)
        return self._timed_result({"stdout": stdout, "stderr": stderr}, start, exit_status=code)

    async def _pull(self, params: dict, start: float) -> ToolResult:
        path = (self._sandbox / params.get("path", ".")).resolve()
        stdout, stderr, code = await self._run_git(["pull"], path)
        return self._timed_result({"stdout": stdout, "stderr": stderr}, start, exit_status=code)
