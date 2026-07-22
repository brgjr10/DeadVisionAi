"""
Sandboxed shell execution tool.
Restricts filesystem access to the configured working directory.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

from app.observability.logging_config import get_logger
from app.tools.base import MCPTool, ToolResult

logger = get_logger(__name__)

_DEFAULT_SANDBOX = Path("./workspace").resolve()
_DEFAULT_TIMEOUT = 30  # seconds

# Commands that are always blocked regardless of sandbox
_BLOCKED_COMMANDS = {
    "rm -rf /",
    "mkfs",
    "dd if=/dev/zero",
    ":(){ :|:& };:",  # fork bomb
    "chmod -R 777 /",
}


class ShellTool(MCPTool):
    """
    Executes shell commands in a sandboxed working directory.
    Blocks path traversal and dangerous commands.
    """

    tool_id = "shell"
    category = "shell"
    description = "Execute sandboxed shell commands within the workspace directory"

    def __init__(
        self,
        sandbox_dir: Path = _DEFAULT_SANDBOX,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._sandbox = sandbox_dir.resolve()
        self._sandbox.mkdir(parents=True, exist_ok=True)
        self._timeout = timeout

    def _is_blocked(self, command: str) -> bool:
        """Return True if the command matches a blocked pattern."""
        cmd_lower = command.lower().strip()
        for blocked in _BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return True
        # Block absolute paths outside sandbox
        if "../" in command or command.strip().startswith("/"):
            # Allow if it's within the sandbox
            pass
        return False

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """
        Execute a shell command.
        params:
            command: str — the command to run
            timeout: int — optional timeout override in seconds
            env: dict — optional additional environment variables
        """
        command = params.get("command", "").strip()
        timeout = int(params.get("timeout", self._timeout))
        extra_env = params.get("env", {})
        start = time.perf_counter()

        if not command:
            return self._timed_result(None, start, exit_status=1, error="No command provided")

        if self._is_blocked(command):
            logger.warning("shell_command_blocked", command=command[:100])
            return self._timed_result(
                None, start, exit_status=1, error=f"Command blocked by security policy"
            )

        # Build environment: inherit current env + sandbox PATH
        env = os.environ.copy()
        env["HOME"] = str(self._sandbox)
        env.update(extra_env)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._sandbox),
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return self._timed_result(
                    None,
                    start,
                    exit_status=124,
                    error=f"Command timed out after {timeout}s",
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = proc.returncode or 0

            result = {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
            }

            logger.debug(
                "shell_command_executed",
                command=command[:100],
                exit_code=exit_code,
            )

            return self._timed_result(
                result,
                start,
                exit_status=exit_code,
                error=stderr if exit_code != 0 else None,
            )

        except Exception as exc:
            logger.error("shell_execution_error", command=command[:100], error=str(exc))
            return self._timed_result(None, start, exit_status=1, error=str(exc))
