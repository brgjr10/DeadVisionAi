import asyncio
import json
from app.tools.registry import get_tool_registry

async def test_web_search_with_known_query():
    """Test web search with a query that should return results"""
    tool_registry = get_tool_registry()
    
    # Test web search with a known working query
    print("Testing web search for 'Python programming language'...")
    params = {
        "query": "Python programming language",
        "max_results": 3
    }
    
    result = await tool_registry.execute_tool("web_search", params)
    print(f"Tool execution success: {result.success}")
    if result.success:
        print(f"Number of results: {len(result.result)}")
        if len(result.result) > 0:
            print(f"First result: {json.dumps(result.result[0], indent=2)[:200]}...")
    else:
        print(f"Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(test_web_search_with_known_query())