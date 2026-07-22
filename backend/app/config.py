"""
HAIOS Application Configuration
All settings are loaded from environment variables via pydantic-settings.
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = Field(default="HAIOS", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    @field_validator('debug', mode='before')
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on', 'debug')
        return bool(v)
    secret_key: str = Field(
        default="change-me-insecure-default",
        description="Secret key for JWT signing and key derivation",
    )
    encryption_key: Optional[str] = Field(
        default=None,
        description="AES-256 encryption key (derived from SECRET_KEY if not set)",
    )

    # --- Database ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///./haios.db",
        description="SQLAlchemy async database URL",
    )

    # --- Redis ---
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # --- Qdrant ---
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant vector store URL",
    )
    qdrant_api_key: Optional[str] = Field(
        default=None,
        description="Qdrant API key (optional for local deployments)",
    )

# --- LM Studio (now pointing to llama.cpp server) ---
    lmstudio_base_url: str = Field(
        default="http://localhost:8080",
        description="LLama.cpp local inference server URL",
        env="LMSTUDIO_BASE_URL",
    )
    lmstudio_model: str = Field(
        default="Llama-3-2-3B-Instruct-Q4_K_S",
        description="Default model identifier for llama.cpp server",
    )
    lmstudio_api_key: str = Field(
        default="lm-studio",
        description="API key for llama.cpp server (not used, but required by provider)",
        env="LMSTUDIO_API_KEY",
    )

    # --- SearXNG ---
    searxng_base_url: str = Field(
        default="http://localhost:8888",
        description="SearXNG search aggregator base URL",
        env="SEARXNG_BASE_URL",
    )

    # --- Cloud Provider API Keys ---
    openrouter_api_key: Optional[str] = Field(default=None)
    groq_api_key: Optional[str] = Field(default=None)
    gemini_api_key: Optional[str] = Field(default=None)
    deepseek_api_key: Optional[str] = Field(default=None)
    together_api_key: Optional[str] = Field(default=None)
    fireworks_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)

    # --- Routing Thresholds ---
    local_complexity_threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Complexity score below which tasks route to local model",
    )
    escalation_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Complexity score at or above which tasks escalate to cloud",
    )
    confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum local model confidence before cloud escalation",
    )
    provider_health_interval: int = Field(
        default=60,
        ge=10,
        description="Seconds between provider health registry refreshes",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        description="Maximum retry attempts per task across providers",
    )

    # --- Cache ---
    cache_ttl_default: int = Field(
        default=3600,
        ge=0,
        description="Default cache TTL in seconds",
    )
    semantic_cache_threshold: float = Field(
        default=0.92,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for semantic cache hits",
    )

    # --- Memory ---
    episodic_token_limit: int = Field(
        default=4000,
        ge=100,
        description="Max tokens in episodic memory before compression",
    )
    memory_top_k: int = Field(
        default=5,
        ge=1,
        description="Number of relevant memories to retrieve",
    )

    # --- Observability ---
    log_level: str = Field(default="INFO", description="Logging level")
    log_retention_days: int = Field(
        default=30,
        ge=1,
        description="Log retention period in days",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    def get_encryption_key(self) -> bytes:
        """
        Return a 32-byte AES-256 key.
        Uses ENCRYPTION_KEY env var if set, otherwise derives from SECRET_KEY via SHA-256.
        """
        if self.encryption_key:
            raw = self.encryption_key.encode()
            return hashlib.sha256(raw).digest()
        return hashlib.sha256(self.secret_key.encode()).digest()

    def get_configured_providers(self) -> dict[str, str]:
        """Return a mapping of provider_id -> api_key for all configured providers."""
        mapping = {
            "openrouter": self.openrouter_api_key,
            "groq": self.groq_api_key,
            "gemini": self.gemini_api_key,
            "deepseek": self.deepseek_api_key,
            "together": self.together_api_key,
            "fireworks": self.fireworks_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
        }

        # --- Free-tier whitelist ---
        # Only providers in this set are eligible for routing. Any configured key
        # belonging to a paid-only account is silently disabled unless explicitly
        # opted-in via FREE_TIER_STRICT=false in the environment.
        free_tier_strict = str(
            os.getenv("FREE_TIER_STRICT", "true")
        ).lower() in ("true", "1", "yes")

        free_providers = {"groq", "openrouter", "gemini", "deepseek", "searxng"}
        paid_providers = {"openai", "anthropic", "together", "fireworks"}

        if free_tier_strict:
            for pid in list(mapping.keys()):
                if pid in paid_providers:
                    from app.observability.logging_config import get_logger as _get_logger
                    _get_logger(__name__).warning(
                        "paid_provider_blocked_in_free_tier_mode",
                        provider_id=pid,
                    )
                    mapping.pop(pid)

        return {k: v for k, v in mapping.items() if v}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()