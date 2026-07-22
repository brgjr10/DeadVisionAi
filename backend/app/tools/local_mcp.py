"""
Local MCP Server Tool Wrapper.
Exposes tools from the local-mcp-server subprocess as MCP tools.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from app.observability.logging_config import get_logger
from app.tools.base import MCPTool, ToolResult
from app.tools.mcp_manager import mcp_manager

logger = get_logger(__name__)


class LocalMCPTool(MCPTool):
    """
    Wrapper that exposes tools from local-mcp-server as individual MCP tools.
    This tool dynamically creates sub-tools based on what's available in the MCP server.
    """
    
    tool_id = "local_mcp"
    category = "mcp"
    description = "Access to local MCP server providing filesystem, shell, SQLite, Brave Search, Context7, and Playwright tools"
    
    def __init__(self) -> None:
        # We don't know the available tools until we start the server
        # This will be populated after initialization
        self._available_tools: Dict[str, Dict[str, Any]] = {}
    
    async def _ensure_initialized(self) -> None:
        """Ensure the MCP manager is started and tools are loaded."""
        await mcp_manager.start()
        # Always refresh our local cache of available tools
        tools = mcp_manager.get_tools()
        self._available_tools = {
            tool["name"]: tool for tool in tools
        }
        logger.info("local_mcp_tools_initialized", count=len(self._available_tools))
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool from the local-mcp-server.
        Expected params: {
            "tool": "tool_name",  # Name of the tool to call (e.g., "read_file")
            "arguments": { ... }  # Arguments for the tool
        }
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            await self._ensure_initialized()
            
            tool_name = params.get("tool")
            arguments = params.get("arguments", {})
            
            if not tool_name:
                return ToolResult(
                    result=None,
                    duration_ms=0.0,
                    exit_status=1,
                    error="Missing 'tool' parameter"
                )
            
            if tool_name not in self._available_tools:
                available = list(self._available_tools.keys())
                return ToolResult(
                    result=None,
                    duration_ms=0.0,
                    exit_status=1,
                    error=f"Unknown tool: {tool_name}. Available tools: {', '.join(available[:10])}{'...' if len(available) > 10 else ''}"
                )
            
            # Call the tool via MCP manager
            result = await mcp_manager.call_tool(tool_name, arguments)
            
            # The MCP server returns results in a specific format
            # We need to extract the content and format it appropriately
            if isinstance(result, dict) and "content" in result:
                content_parts = result["content"]
                if isinstance(content_parts, list) and len(content_parts) == 1:
                    # Single text result
                    text_content = content_parts[0].get("text", "")
                    return ToolResult(
                        result=text_content,
                        duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000
                    )
                else:
                    # Multiple parts or non-text - return as structured data
                    return ToolResult(
                        result=content_parts,
                        duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000
                    )
            else:
                # Unexpected format - return as-is
                return ToolResult(
                    result=result,
                    duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000
                )
                
        except Exception as exc:
            logger.error("local_mcp_tool_error", tool=params.get("tool"), error=str(exc))
            return ToolResult(
                result=None,
                duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
                exit_status=1,
                error=str(exc)
            )


# For backward compatibility, also create individual tool classes
# that map to specific local-mcp-server tools

class LocalMCPFilesystemTool(LocalMCPTool):
    """Filesystem operations via local-mcp-server."""
    
    tool_id = "local_mcp_filesystem"
    category = "filesystem"
    description = "Filesystem operations (read_file, write_file, list_directory, search_files) via local-mcp-server"
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        # Map filesystem operations to the MCP server
        operation = params.get("operation")
        if not operation:
            return ToolResult(
                result=None,
                duration_ms=0.0,
                exit_status=1,
                error="Missing 'operation' parameter"
            )
        
        # Map to MCP server tool names
        tool_map = {
            "read_file": "read_file",
            "write_file": "write_file", 
            "list_directory": "list_directory",
            "search_files": "search_files"
        }
        
        if operation not in tool_map:
            return ToolResult(
                result=None,
                duration_ms=0.0,
                exit_status=1,
                error=f"Unknown filesystem operation: {operation}"
            )
        
        # Prepare arguments for the MCP server tool
        mcp_args = {}
        if operation == "read_file":
            mcp_args = {"file_path": params.get("path", "")}
        elif operation == "write_file":
            mcp_args = {
                "file_path": params.get("path", ""),
                "content": params.get("content", ""),
                "mode": params.get("mode", "w")
            }
        elif operation == "list_directory":
            mcp_args = {"dir_path": params.get("path", ".")}
        elif operation == "search_files":
            mcp_args = {
                "dir_path": params.get("path", "."),
                "pattern": params.get("pattern", "*"),
                "recursive": params.get("recursive", True)
            }
        
        # Call the MCP server tool
        return await super().execute({
            "tool": tool_map[operation],
            "arguments": mcp_args
        })


class LocalMCPShellTool(LocalMCPTool):
    """Shell command execution via local-mcp-server."""
    
    tool_id = "local_mcp_shell"
    category = "shell"
    description = "Execute shell commands via local-mcp-server"
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        command = params.get("command")
        if not command:
            return ToolResult(
                result=None,
                duration_ms=0.0,
                exit_status=1,
                error="Missing 'command' parameter"
            )
        
        mcp_args = {
            "command": command,
            "cwd": params.get("cwd"),
            "timeout_ms": params.get("timeout_ms", 15000)
        }
        
        # Remove None values
        mcp_args = {k: v for k, v in mcp_args.items() if v is not None}
        
        return await super().execute({
            "tool": "run_command",
            "arguments": mcp_args
        })