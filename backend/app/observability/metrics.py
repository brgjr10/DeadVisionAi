"""
Prometheus metrics definitions for HAIOS.
All metrics are registered here and imported by subsystems.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, REGISTRY

# Use the default registry
_registry = REGISTRY

# --- API Gateway Metrics ---
request_total = Counter(
    "haios_request_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

request_duration_seconds = Histogram(
    "haios_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

active_sessions = Gauge(
    "haios_active_sessions",
    "Number of currently active sessions",
)

# --- Provider Metrics ---
provider_requests_total = Counter(
    "haios_provider_requests_total",
    "Total requests sent to AI providers",
    ["provider_id", "model_id", "status"],
)

provider_latency_seconds = Histogram(
    "haios_provider_latency_seconds",
    "Provider response latency in seconds",
    ["provider_id"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

provider_cooldown_total = Counter(
    "haios_provider_cooldown_total",
    "Number of times a provider entered cooldown",
    ["provider_id"],
)

# --- Cache Metrics ---
cache_hits_total = Counter(
    "haios_cache_hits_total",
    "Total cache hits",
    ["cache_type"],  # "exact" or "semantic"
)

cache_misses_total = Counter(
    "haios_cache_misses_total",
    "Total cache misses",
    ["cache_type"],
)

cache_evictions_total = Counter(
    "haios_cache_evictions_total",
    "Total cache evictions",
)

# --- Token Usage Metrics ---
token_usage_total = Counter(
    "haios_token_usage_total",
    "Total tokens consumed",
    ["provider_id", "session_id"],
)

# --- Tool Metrics ---
tool_executions_total = Counter(
    "haios_tool_executions_total",
    "Total MCP tool executions",
    ["tool_id", "status"],
)

tool_duration_seconds = Histogram(
    "haios_tool_duration_seconds",
    "MCP tool execution duration in seconds",
    ["tool_id"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 30.0],
)

# --- Agent Metrics ---
agent_task_completions_total = Counter(
    "haios_agent_task_completions_total",
    "Total agent task completions",
    ["agent_role", "status"],
)

# --- Memory Metrics ---
memory_retrievals_total = Counter(
    "haios_memory_retrievals_total",
    "Total memory retrieval operations",
    ["memory_type"],
)
