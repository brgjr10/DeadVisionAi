"""
HAIOS Backend Application Entry Point.
Initializes all subsystems and starts the FastAPI server.
"""
from __future__ import annotations

import asyncio
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.gateway.router import router as gateway_router
from app.gateway.middleware import RequestIDMiddleware, RateLimitMiddleware
from app.memory.manager import get_memory_manager
from app.memory.episodic import get_episodic_memory
from app.memory.semantic import get_semantic_memory
from app.memory.vector_store import get_vector_store
from app.cache.redis_cache import get_redis_cache
from app.providers.registry import get_provider_registry
from app.providers.litellm_adapter import LiteLLMProvider
from app.providers.llamacpp_provider import LlamaCppProvider
from app.providers.searxng_provider import SearXNGProvider
from app.routing.master_router import get_master_router
from app.routing.classifier import get_task_classifier
from app.classifier.rdocl import ModelVersionDetector, SchemaHealthCheck, get_version_detector, get_schema_health_check
from app.classifier.classifier_keepalive import ClassifierKeepAlive, get_classifier_keepalive
from app.tools.registry import get_tool_registry
from app.tools.filesystem import FilesystemTool
from app.tools.shell import ShellTool
from app.tools.git_tools import GitTool
from app.tools.web_search import WebSearchTool
from app.observability.logging_config import configure_logging, get_logger
from app.observability.metrics import request_total, request_duration_seconds

logger = get_logger(__name__)


# Suppress specific Qdrant warnings during startup
warnings.filterwarnings("ignore", message="Failed to obtain server version.*", category=UserWarning)


async def _initialize_providers() -> None:
    """Initialize and register all cloud providers from config."""
    settings = get_settings()
    registry = get_provider_registry()

    # Default models per provider (matching master_router._PROVIDER_DEFAULT_MODELS)
    DEFAULT_MODELS = {
        "openrouter": "openrouter/google/gemini-2.0-flash-001",
        "groq": "groq/llama-3.1-8b-instant",
        "deepseek": "deepseek/deepseek-chat",
        "gemini": "gemini/gemini-2.0-flash-lite",
        "together": "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "fireworks": "fireworks_ai/accounts/fireworks/models/llama-v3p1-405b-instruct",
        "openai": "openai/gpt-4o-mini",
        "anthropic": "anthropic/claude-3-5-sonnet-20241022",
    }

    for provider_id, api_key in settings.get_configured_providers().items():
        if not api_key:
            continue

        from app.security.encryption import encrypt_api_key

        encrypted_key = encrypt_api_key(api_key)
        model_id = DEFAULT_MODELS.get(provider_id, f"{provider_id}/default")
        provider = LiteLLMProvider(
            provider_id=provider_id,
            model_id=model_id,
            encrypted_api_key=encrypted_key,
            session_id="system",
        )
        registry.register_sync(provider)
        logger.info("provider_initialized", provider_id=provider_id)

    # Initialize local llama.cpp provider
    llamacpp = LlamaCppProvider(
        provider_id="llamacpp",
        model_id=settings.lmstudio_model,
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
    )
    registry.register_sync(llamacpp)
    logger.info("llamacpp_provider_initialized")

    # Initialize SearXNG — always free, no API key needed
    searxng = SearXNGProvider(provider_id="searxng")
    registry.register_sync(searxng)
    logger.info("searxng_provider_initialized")

    # Start health monitor
    get_master_router().start_health_monitor()
    logger.info("health_monitor_started")


async def _initialize_tools() -> None:
    """Register all MCP tools."""
    tool_registry = get_tool_registry()

    tool_registry.register(FilesystemTool())
    tool_registry.register(ShellTool())
    tool_registry.register(GitTool())
    tool_registry.register(WebSearchTool())
    
    # Register local MCP server tools
    from app.tools.local_mcp import LocalMCPFilesystemTool, LocalMCPShellTool, LocalMCPTool
    tool_registry.register(LocalMCPFilesystemTool())
    tool_registry.register(LocalMCPShellTool())
    tool_registry.register(LocalMCPTool())  # Generic tool for accessing all MCP server tools

    logger.info(
        "tools_initialized",
        count=len(tool_registry.list_tools()),
    )


async def _initialize_memory() -> None:
    """Initialize memory subsystems."""
    memory_manager = get_memory_manager()
    # This will handle Qdrant unavailability gracefully
    await get_vector_store().ensure_collection_exists()
    logger.info("memory_subsystems_initialized")


async def _initialize_rdocl() -> None:
    """Start classifier-version and schema-health background watchers."""
    settings = get_settings()

    # ModelVersionDetector — watches for LM Studio model swaps
    version_detector = get_version_detector(
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
        interval=int(getattr(settings, "rdocl_interval_seconds", 60)),
    )
    version_detector.start()

    # SchemaHealthCheck — probes the local model every interval for schema drift
    schema_check = get_schema_health_check(
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
        model=settings.lmstudio_model,
        interval=int(getattr(settings, "rdocl_interval_seconds", 60)),
    )
    schema_check.start()

    # ClassifierKeepAlive — prevents LM Studio from offloading the classifier model
    keepalive = get_classifier_keepalive(
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
    )
    keepalive.start()

    logger.info("rdocl_watchers_started")


async def _shutdown_rdocl() -> None:
    """Stop classifier watchers and keep-alive on shutdown."""
    global _detector, _health
    if _detector:
        _detector.stop()
    if _health:
        _health.stop()
    get_classifier_keepalive().stop()
    logger.info("rdocl_watchers_stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("haios_startup", version=settings.app_version)

    # Initialize providers and tools
    await _initialize_providers()
    await _initialize_tools()
    await _initialize_memory()
    await _initialize_rdocl()   # starts model-version + schema watchers

    yield

    # Cleanup on shutdown
    await _shutdown_rdocl()      # stop rdocl watchers first
    await get_redis_cache().close()
    get_master_router().stop_health_monitor()
    logger.info("haios_shutdown")


app = FastAPI(
    title="HAIOS API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(gateway_router)


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {"message": "HAIOS API is running", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")