import asyncio
import json
from app.tools.registry import get_tool_registry

async def test_web_search_tool():
    """Test the web search tool directly"""
    tool_registry = get_tool_registry()
    print(f"Available tools: {[t['tool_id'] for t in tool_registry.list_tools()]}")
    
    # Test web search
    print("\nTesting web search for 'current time in Japan'...")
    params = {
        "query": "current time in Japan",
        "max_results": 3
    }
    
    result = await tool_registry.execute_tool("web_search", params)
    print(f"Tool execution success: {result.success}")
    if result.success:
        print(f"Results: {json.dumps(result.result, indent=2)}")
    else:
        print(f"Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(test_web_search_tool())