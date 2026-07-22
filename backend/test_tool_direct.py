import asyncio
import json
from app.tools.registry import get_tool_registry
from app.routing.classifier import get_task_classifier

async def test_tool_execution():
    """Test tool execution directly"""
    print("Testing tool execution...")
    
    # Test classifier
    classifier = get_task_classifier()
    classification = await classifier.classify("what time is it in japan?", [])
    print(f"Classification: intent={classification.intent}, complexity={classification.complexity_score}")
    print(f"Recommended tools: {classification.recommended_tools}")
    
    # Test tool registry and execution
    tool_registry = get_tool_registry()
    print(f"Available tools: {[t['tool_id'] for t in tool_registry.list_tools()]}")
    
    if classification.recommended_tools:
        for tool_id in classification.recommended_tools:
            if tool_id in tool_registry._tools:
                print(f"Executing tool: {tool_id}")
                params = {"query": "what time is it in japan?", "max_results": 3}
                result = await tool_registry.execute_tool(tool_id, params)
                print(f"Tool result: success={result.success}")
                if result.success:
                    print(f"Result data: {json.dumps(result.result, indent=2)[:500]}...")
                else:
                    print(f"Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(test_tool_execution())