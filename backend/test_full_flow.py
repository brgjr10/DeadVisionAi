import asyncio
import json
from app.routing.classifier import get_task_classifier
from app.routing.master_router import get_master_router
from app.tools.registry import get_tool_registry
from app.providers.registry import get_provider_registry

async def test_full_flow():
    """Test the full flow: classification -> tool execution -> routing -> provider"""
    print("=== Testing Full Flow ===")
    
    # 1. Classification
    classifier = get_task_classifier()
    message = "what time is it in japan?"
    classification = await classifier.classify(message, context=[])
    print(f"1. Classification:")
    print(f"   Intent: {classification.intent}")
    print(f"   Complexity: {classification.complexity_score}")
    print(f"   Recommended tools: {classification.recommended_tools}")
    
    # 2. Tool Execution
    print(f"\n2. Tool Execution:")
    tool_registry = get_tool_registry()
    available_tools = tool_registry.list_tools()
    print(f"   Available tools: {[t['tool_id'] for t in available_tools]}")
    
    tool_results = {}
    if classification.recommended_tools:
        for tool_id in classification.recommended_tools:
            # Find the tool
            tool = None
            for t in tool_registry._tools.values():
                if t.tool_id == tool_id:
                    tool = t
                    break
            
            if tool:
                print(f"   Executing tool: {tool_id}")
                params = {"query": message, "max_results": 3}
                result = await tool.execute(params)
                if result.success:
                    tool_results[tool_id] = result.result
                    print(f"   Success: Got {len(result.result) if isinstance(result.result, list) else 1} results")
                else:
                    print(f"   Error: {result.error}")
            else:
                print(f"   Tool {tool_id} not found in registry")
    
    # 3. Routing Decision
    print(f"\n3. Routing Decision:")
    from app.gateway.schemas import TaskRequest
    task_request = TaskRequest(content=message, stream=False)
    master_router = get_master_router()
    decision = await master_router.route(task_request, classification)
    print(f"   Selected provider: {decision.provider_id}")
    print(f"   Selected model: {decision.model_id}")
    print(f"   Routing reason: {decision.routing_reason}")
    
    # 4. Provider Selection
    print(f"\n4. Provider Selection:")
    provider_registry = get_provider_registry()
    provider = provider_registry.get_by_id(decision.provider_id)
    if provider:
        print(f"   Provider found: {provider.provider_id}")
        print(f"   Provider model: {provider.model_id}")
    else:
        print(f"   Provider '{decision.provider_id}' not found!")
        # List available providers
        providers = provider_registry.list_all()
        print(f"   Available providers: {[p['provider_id'] for p in providers]}")
    
    # 5. Final Assessment
    print(f"\n5. Assessment:")
    if tool_results:
        print(f"   ✓ Tools were executed successfully: {list(tool_results.keys())}")
        print(f"   ✓ System should use tool results for accurate time information")
    else:
        print(f"   ✗ No tools were executed - will rely on AI model's internal knowledge")
        print(f"   ✗ This explains why you're getting generic time information")

if __name__ == "__main__":
    asyncio.run(test_full_flow())