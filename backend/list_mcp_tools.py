import asyncio
from app.tools.mcp_manager import mcp_manager

async def list_mcp_tools():
    """List all available tools from the local MCP server"""
    print("Starting MCP manager...")
    await mcp_manager.start()
    
    print("Getting available tools...")
    tools = mcp_manager.get_tools()
    
    print(f"\nFound {len(tools)} tools:")
    for i, tool in enumerate(tools, 1):
        print(f"{i:2d}. {tool['name']}")
        print(f"    Description: {tool.get('description', 'No description')}")
        print()

if __name__ == "__main__":
    asyncio.run(list_mcp_tools())