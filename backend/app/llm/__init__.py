"""
Unified LLM Client & Runtime Failover package for PitWall AI.
"""

from backend.app.llm.failover_client import (
    LLMResult,
    generate_with_failover,
    stream_with_failover,
    get_ollama_chat_url,
    get_gemini_config,
    get_active_provider_hint,
    is_gemini_in_cooldown,
    reset_gemini_cooldown,
)

__all__ = [
    "LLMResult",
    "generate_with_failover",
    "stream_with_failover",
    "get_ollama_chat_url",
    "get_gemini_config",
    "get_active_provider_hint",
    "is_gemini_in_cooldown",
    "reset_gemini_cooldown",
]
