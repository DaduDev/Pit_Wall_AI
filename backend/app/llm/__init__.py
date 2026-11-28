"""
Unified LLM Client & 4-Tier Cascading Runtime Failover package for PitWall AI.
"""

from backend.app.llm.failover_client import (
    LLMResult,
    PROVIDER_LABELS,
    generate_with_failover,
    stream_with_failover,
    get_ollama_chat_url,
    get_gemini_config,
    get_groq_config,
    get_openrouter_config,
    get_active_provider_hint,
    is_ollama_fallback_enabled,
    is_provider_in_cooldown,
    record_provider_429_cooldown,
    reset_provider_cooldown,
    is_gemini_in_cooldown,
    reset_gemini_cooldown,
)

__all__ = [
    "LLMResult",
    "PROVIDER_LABELS",
    "generate_with_failover",
    "stream_with_failover",
    "get_ollama_chat_url",
    "get_gemini_config",
    "get_groq_config",
    "get_openrouter_config",
    "get_active_provider_hint",
    "is_ollama_fallback_enabled",
    "is_provider_in_cooldown",
    "record_provider_429_cooldown",
    "reset_provider_cooldown",
    "is_gemini_in_cooldown",
    "reset_gemini_cooldown",
]
