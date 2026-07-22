"""
Manager for the local-mcp-server subprocess.
"""
from __future__ import annotations

import json
import os
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.observability.logging_config import get_logger

logger = get_logger(__name__)

LOCAL_MCP_SERVER_PATH = Path(os.getenv(
    "LOCAL_MCP_SERVER_PATH",
    r"F:\MCP Database\local-mcp-server"
))


class MCPManager:
    """Manages the local-mcp-server subprocess and communication."""
    
    _instance: Optional["MCPManager"] = None
    _process: Optional[asyncio.subprocess.Process] = None
    _initialized: bool = False
    _tools: List[Dict[str, Any]] = []
    _tools_loaded_event: Optional[asyncio.Event] = None
    
    def __new__(cls) -> "MCPManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def start(self) -> None:
        """Start the local-mcp-server subprocess if not already running."""
        if self._process is not None:
            return
            
        server_path = LOCAL_MCP_SERVER_PATH / "server.js"
        if not server_path.exists():
            raise FileNotFoundError(
                f"local-mcp-server not found at {server_path}. "
                "Set LOCAL_MCP_SERVER_PATH environment variable correctly."
            )
        
        logger.info("starting_local_mcp_server", path=str(server_path))
        
        # Create event to signal when tools are loaded
        self._tools_loaded_event = asyncio.Event()
        
        # Use node to run the server
        self._process = await asyncio.create_subprocess_exec(
            "node", str(server_path),
            cwd=str(LOCAL_MCP_SERVER_PATH),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        # Log stderr output for debugging
        asyncio.create_task(self._log_stderr())
        
        # Initialize and get tool list
        await self._initialize()
        logger.info("local_mcp_server_started")
    
    async def _log_stderr(self) -> None:
        """Log stderr output from the MCP server for debugging."""
        if self._process and self._process.stderr:
            while True:
                line = await self._process.stderr.readline()
                if not line:
                    break
                logger.debug("mcp_server_stderr", line=line.decode().rstrip())
    
    async def _initialize(self) -> None:
        """Initialize the server and fetch available tools."""
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("MCP server process not available")
            
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "haios-backend", "version": "0.1.0"}
            }
        }
        
        try:
            await self._send_request(init_request)
            # Send tools/list request
            await self._refresh_tools()
            self._initialized = True
            logger.info("mcp_tools_loaded", count=len(self._tools))
        except Exception as e:
            logger.error("mcp_initialization_failed", error=str(e))
            await self.stop()
            raise
    
    async def _refresh_tools(self) -> None:
        """Refresh the tool list from the MCP server."""
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("MCP server process not available")
            
        # Send tools/list request
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        result = await self._send_request(list_request)
        # Extract tools from the result
        if isinstance(result, dict) and "result" in result:
            self._tools = result["result"].get("tools", [])
        else:
            self._tools = result.get("tools", []) if isinstance(result, dict) else []
        
        # Signal that tools have been loaded (at least the initial set)
        if self._tools_loaded_event:
            self._tools_loaded_event.set()
        
        logger.debug("tools_refreshed", count=len(self._tools))
    
    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and return the result."""
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("MCP server process not available")
            
        request_bytes = (json.dumps(request) + "\n").encode()
        self._process.stdin.write(request_bytes)
        await self._process.stdin.drain()
        
        # Read response line
        response_line = await self._process.stdout.readline()
        if not response_line:
            raise RuntimeError("MCP server closed connection")
            
        response = json.loads(response_line.decode())
        if "error" in response:
            raise RuntimeError(f"MCP server error: {response['error']}")
        return response.get("result", {})
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        if not self._initialized:
            await self.start()
            
        # Wait for tools to be loaded (with timeout)
        if self._tools_loaded_event:
            try:
                await asyncio.wait_for(self._tools_loaded_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("timeout_waiting_for_tools_to_load")
        
        request = {
            "jsonrpc": "2.0",
            "id": 3,  # We'll use a fixed ID for simplicity; in production should increment
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }
        
        result = await self._send_request(request)
        return result
    
    async def stop(self) -> None:
        """Stop the MCP server subprocess."""
        if self._process is not None:
            logger.info("stopping_local_mcp_server")
            self._process.terminate()
            try:
                await self._process.wait()
            except Exception:
                self._process.kill()
                await self._process.wait()
            self._process = None
            self._initialized = False
            if self._tools_loaded_event:
                self._tools_loaded_event.clear()
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get the list of available tools from the MCP server."""
        return self._tools


# Singleton instance
mcp_manager = MCPManager()