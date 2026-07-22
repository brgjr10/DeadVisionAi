import asyncio
import json
from contextlib import asynccontextmanager

# Import app components
from app.config import get_settings
from app.observability.logging_config import configure_logging
from app.routing.classifier import get_task_classifier
from app.routing.master_router import get_master_router
from app.tools.registry import get_tool_registry
from app.providers.registry import get_provider_registry
from app.tools.local_mcp import LocalMCPFilesystemTool, LocalMCPShellTool, LocalMCPTool
from app.tools.web_search import WebSearchTool
from app.tools.filesystem import FilesystemTool
from app.tools.shell import ShellTool
from app.tools.git_tools import GitTool
from app.tools.mcp_manager import mcp_manager

async def initialize_app():
    """Initialize the application components like main.py does"""
    print("Initializing application components...")
    
    # Initialize logging
    settings = get_settings()
    configure_logging(settings.log_level)
    
    # Initialize tools (like in _initialize_tools)
    tool_registry = get_tool_registry()
    
    # Register standard tools
    tool_registry.register(FilesystemTool())
    tool_registry.register(ShellTool())
    tool_registry.register(GitTool())
    tool_registry.register(WebSearchTool())
    
    # Initialize and register local MCP tools
    await mcp_manager.start()
    tool_registry.register(LocalMCPFilesystemTool())
    tool_registry.register(LocalMCPShellTool())
    tool_registry.register(LocalMCPTool())  # Generic tool for accessing all MCP server tools
    
    print(f"Tools initialized: {[t['tool_id'] for t in tool_registry.list_tools()]}")
    
    # Initialize providers (like in _initialize_providers)
    from app.providers.litellm_adapter import LiteLLMProvider
    from app.providers.lmstudio_provider import LMStudioProvider
    
    registry = get_provider_registry()
    
    # Initialize cloud providers from config
    for provider_id, api_key in settings.get_configured_providers().items():
        if not api_key:
            continue
            
        from app.security.encryption import encrypt_api_key
        
        encrypted_key = encrypt_api_key(api_key)
        provider = LiteLLMProvider(
            provider_id=provider_id,
            model_id=f"{provider_id}/default",
            encrypted_api_key=encrypted_key,
            session_id="system",
        )
        registry.register_sync(provider)
        print(f"Provider initialized: {provider_id}")
    
    # Initialize local LM Studio provider
    lmstudio = LMStudioProvider(
        provider_id="lmstudio",
        model_id=settings.lmstudio_model,
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
    )
    registry.register_sync(lmstudio)
    print("Provider initialized: lmstudio")
    
    # Start health monitor
    get_master_router().start_health_monitor()
    print("Health monitor started")
    
    print("Application initialization complete!")

async def test_full_flow():
    """Test the full flow: classification -> tool execution -> routing -> provider"""
    print("=== Testing Full Flow ===")
    
    # Initialize app first
    await initialize_app()
    
    # 1. Classification
    classifier = get_task_classifier()
    message = "what time is it in japan?"
    classification = await classifier.classify(message, context=[])
    print(f"\n1. Classification:")
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
                    if isinstance(result.result, list) and len(result.result) > 0:
                        print(f"   First result preview: {str(result.result[0])[:200]}...")
                else:
                    print(f"   Error: {result.error}")
            else:
                print(f"   Tool {tool_id} not found in registry")
    
    # 3. Show tool results
    print(f"\n3. Tool Results Summary:")
    for tool_id, result in tool_results.items():
        print(f"   {tool_id}: {type(result).__name__} with {len(result) if hasattr(result, '__len__') else 'N/A'} items")
        if isinstance(result, list) and len(result) > 0:
            print(f"     Sample: {str(result[0])[:100]}...")
    
    # 4. Routing Decision
    print(f"\n4. Routing Decision:")
    from app.gateway.schemas import TaskRequest
    task_request = TaskRequest(
        session_id="test-session-123",
        content=message, 
        stream=False
    )
    master_router = get_master_router()
    decision = await master_router.route(task_request, classification)
    print(f"   Selected provider: {decision.provider_id}")
    print(f"   Selected model: {decision.model_id}")
    print(f"   Routing reason: {decision.routing_reason}")
    print(f"   Fallback chain: {decision.fallback_chain}")
    
    # 5. Provider Selection
    print(f"\n5. Provider Selection:")
    provider_registry = get_provider_registry()
    provider = provider_registry.get_by_id(decision.provider_id)
    if provider:
        print(f"   Provider found: {provider.provider_id}")
        print(f"   Provider model: {provider.model_id}")
        print(f"   Provider available: {provider.is_available}")
    else:
        print(f"   Provider '{decision.provider_id}' not found!")
        # List available providers
        providers = provider_registry.list_all()
        print(f"   Available providers: {[p['provider_id'] for p in providers]}")
    
    # 6. Final Assessment
    print(f"\n6. Final Assessment:")
    web_search_executed = 'web_search' in tool_results
    local_mcp_available = any('local_mcp' in str(t['tool_id']) for t in tool_registry.list_tools())
    
    if web_search_executed:
        if len(tool_results.get('web_search', [])) > 0:
            print(f"   [OK] Web search tool was executed successfully")
            print(f"   [OK] System has real-time information for accurate time response")
        else:
            print(f"   [WARNING] Web search tool executed but returned no results")
            print(f"   [INFO] This might indicate a connectivity issue or query problem")
    elif local_mcp_available:
        print(f"   [INFO] Local MCP server is available - could use brave_search or other tools")
        print(f"   [NOTE] Web search not in recommended tools, but MCP server might have search capabilities")
    else:
        print(f"   [ERROR] No search tools executed - will rely on AI model's internal knowledge")
        print(f"   [ERROR] This explains why you're getting generic time information")
    
    print(f"\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_full_flow())