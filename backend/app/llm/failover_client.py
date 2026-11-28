"""
4-Tier Cascading LLM Runtime Failover Helper for PitWall AI.
Used across PitWallEngineer, HistoricalSQLAgent, and ResearchAgent.

Cascade order (both sync and streaming):
  1. Gemini (primary, env/Vertex AI driven, supports google_search grounding) -> provider="gemini"
  2. Groq (OpenAI-compatible /chat/completions, timeout=30.0, trimmed context for 8K TPM) -> provider="groq_fallback"
  3. OpenRouter (OpenAI-compatible /chat/completions, timeout=35.0, optional HTTP-Referer & X-Title) -> provider="openrouter_fallback"
  4. Local Ollama over IPv4 (qwen3.5:4b, num_ctx=1024, num_predict=180, think=False, timeout=150.0)
     ONLY when ENABLE_OLLAMA_FALLBACK resolves to True (True when APP_ENV != "production") -> provider="ollama_fallback"

Features:
- Independent 60s HTTP 429 cooldown circuit breakers for "gemini", "groq", and "openrouter".
- Server-side warning logging for all provider errors; zero raw JSON/429 leaks into UI text.
- Explicit provider provenance: "gemini" | "cache" | "groq_fallback" | "openrouter_fallback" | "ollama_fallback".
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx

from backend.app.config import (
    settings,
    build_thinking_config,
    is_unsupported_thinking_error,
)

logger = logging.getLogger("pitwall.llm.failover")

_CLIENT_CACHE: Dict[Tuple[Any, ...], Any] = {}
_LAST_GEMINI_FAILOVER_AT: float = 0.0
_PROVIDER_COOLDOWN_UNTIL: Dict[str, float] = {}

PROVIDER_429_COOLDOWN_SECONDS: float = 60.0
GEMINI_429_COOLDOWN_SECONDS: float = PROVIDER_429_COOLDOWN_SECONDS
GROQ_MAX_PROMPT_CHARS: int = 12000  # Trims context safely under Groq's 8K TPM budget
GROQ_MAX_SYSTEM_CHARS: int = 2000

OLLAMA_DEFAULT_OPTIONS: Dict[str, Any] = {
    "num_ctx": 1024,
    "num_predict": 180,
    "temperature": 0.3,
}

PROVIDER_LABELS: Dict[str, str] = {
    "gemini": "Google Search Grounding",
    "cache": "Cached Search Grounding",
    "groq_fallback": "Groq Cloud Fallback — No Live Search",
    "openrouter_fallback": "OpenRouter Free Fallback — No Live Search",
    "ollama_fallback": "Local Ollama Fallback — Offline Model",
}


def _resolve_env_or_setting(key: str, default: Any = None) -> Any:
    """Resolve configuration value preferring live os.environ over static Settings."""
    if key in os.environ:
        return os.environ[key]
    val = getattr(settings, key, None)
    if val is None or val == "":
        return default
    return val


def is_ollama_fallback_enabled() -> bool:
    """
    Determine whether Tier 4 local Ollama fallback is enabled.
    Defaults to True when APP_ENV != "production" and False when APP_ENV == "production".
    Explicit ENABLE_OLLAMA_FALLBACK env/setting overrides APP_ENV default.
    """
    if "ENABLE_OLLAMA_FALLBACK" in os.environ:
        raw = os.environ["ENABLE_OLLAMA_FALLBACK"].strip().lower()
        if raw in ("1", "true", "yes", "on"):
            return True
        if raw in ("0", "false", "no", "off"):
            return False

    if "APP_ENV" in os.environ:
        return os.environ["APP_ENV"].strip().lower() != "production"

    app_env = str(getattr(settings, "APP_ENV", "local") or "local").strip().lower()
    explicit = getattr(settings, "ENABLE_OLLAMA_FALLBACK", None)
    if explicit is not None:
        return bool(explicit)
    return app_env != "production"


def record_gemini_failover() -> None:
    """Record timestamp of most recent runtime Gemini failover."""
    global _LAST_GEMINI_FAILOVER_AT
    _LAST_GEMINI_FAILOVER_AT = time.time()


def record_provider_429_cooldown(
    provider: str,
    seconds: float = PROVIDER_429_COOLDOWN_SECONDS,
) -> None:
    """Enter 60s circuit-breaker cooldown for a specific cloud provider ('gemini' | 'groq' | 'openrouter')."""
    _PROVIDER_COOLDOWN_UNTIL[provider.lower()] = time.time() + seconds


def is_provider_in_cooldown(provider: str) -> bool:
    """Return True if the specified provider is inside its 60s 429 cooldown window."""
    until = _PROVIDER_COOLDOWN_UNTIL.get(provider.lower(), 0.0)
    return until > 0 and time.time() < until


def reset_provider_cooldown(provider: Optional[str] = None) -> None:
    """Reset cooldown state for a specific provider, or all providers when omitted."""
    global _LAST_GEMINI_FAILOVER_AT
    if provider is None:
        _PROVIDER_COOLDOWN_UNTIL.clear()
        _LAST_GEMINI_FAILOVER_AT = 0.0
    else:
        _PROVIDER_COOLDOWN_UNTIL.pop(provider.lower(), None)
        if provider.lower() == "gemini":
            _LAST_GEMINI_FAILOVER_AT = 0.0


def record_gemini_429_cooldown(seconds: float = GEMINI_429_COOLDOWN_SECONDS) -> None:
    """Backward-compatible wrapper entering Gemini 60s 429 cooldown."""
    record_provider_429_cooldown("gemini", seconds)


def reset_gemini_cooldown() -> None:
    """Backward-compatible helper clearing all provider cooldowns (used by pytest autouse fixture)."""
    reset_provider_cooldown(None)


def is_gemini_in_cooldown() -> bool:
    """Backward-compatible check returning True when Gemini is in 429 cooldown."""
    return is_provider_in_cooldown("gemini")


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detect HTTP 429 / RESOURCE_EXHAUSTED / rate-limit errors cleanly."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        if exc.response.status_code == 429:
            return True
    msg = str(exc).lower()
    return "429" in msg or "resource_exhausted" in msg or "rate limit" in msg or "quota" in msg


def get_gemini_config() -> Dict[str, Any]:
    """Read purely env-driven Gemini / Vertex AI configuration."""
    api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or getattr(settings, "GEMINI_API_KEY", "")
        or getattr(settings, "GOOGLE_API_KEY", "")
    )
    if not api_key:
        try:
            from dotenv import dotenv_values
            env_vals = dotenv_values(".env")
            api_key = env_vals.get("GEMINI_API_KEY") or env_vals.get("GOOGLE_API_KEY") or ""
        except Exception:
            api_key = ""

    use_vertex_raw = os.environ.get(
        "GOOGLE_GENAI_USE_VERTEXAI",
        str(getattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", False)),
    )
    use_vertex = str(use_vertex_raw).strip().lower() in ("1", "true", "yes")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or getattr(settings, "GOOGLE_CLOUD_PROJECT", "")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION") or getattr(settings, "GOOGLE_CLOUD_LOCATION", "us-central1")
    model = os.environ.get("GEMINI_MODEL") or getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite")
    provider_mode = (os.environ.get("LLM_PROVIDER") or getattr(settings, "LLM_PROVIDER", "gemini")).lower()

    return {
        "api_key": api_key,
        "use_vertex": use_vertex,
        "project": project,
        "location": location,
        "model": model,
        "provider_mode": provider_mode,
    }


def get_groq_config() -> Dict[str, str]:
    """Resolve Groq OpenAI-compatible fallback configuration."""
    return {
        "api_key": str(_resolve_env_or_setting("GROQ_API_KEY", "") or "").strip(),
        "base_url": str(_resolve_env_or_setting("GROQ_BASE_URL", "https://api.groq.com/openai/v1")).strip().rstrip("/"),
        "model": str(_resolve_env_or_setting("GROQ_MODEL", "openai/gpt-oss-120b")).strip(),
    }


def get_openrouter_config() -> Dict[str, str]:
    """Resolve OpenRouter OpenAI-compatible fallback configuration."""
    return {
        "api_key": str(_resolve_env_or_setting("OPENROUTER_API_KEY", "") or "").strip(),
        "base_url": str(_resolve_env_or_setting("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")).strip().rstrip("/"),
        "model": str(_resolve_env_or_setting("OPENROUTER_MODEL", "openrouter/free")).strip(),
        "http_referer": str(_resolve_env_or_setting("OPENROUTER_HTTP_REFERER", "") or "").strip(),
    }


def get_ollama_chat_url() -> str:
    """Resolve Ollama /api/chat URL from OLLAMA_BASE_URL or OLLAMA_API_BASE without duplicating /api/chat."""
    raw_url = os.environ.get("OLLAMA_BASE_URL") or getattr(settings, "OLLAMA_BASE_URL", "")
    if not raw_url:
        raw_url = os.environ.get("OLLAMA_API_BASE") or getattr(settings, "OLLAMA_API_BASE", "http://127.0.0.1:11434")
    clean = raw_url.strip().rstrip("/")
    while clean.endswith("/api/chat"):
        clean = clean[: -len("/api/chat")].rstrip("/")
    return f"{clean}/api/chat"


def get_ollama_model() -> str:
    """Resolve configured local Ollama model name."""
    return os.environ.get("OLLAMA_MODEL") or getattr(settings, "OLLAMA_MODEL", "qwen3.5:4b")


def get_active_provider_hint() -> str:
    """Predict the highest-priority active provider respecting cooldowns and environment gating."""
    cfg = get_gemini_config()
    if cfg["provider_mode"] == "ollama":
        if is_ollama_fallback_enabled():
            return "ollama_fallback"

    gemini_ready = (
        cfg["provider_mode"] != "ollama"
        and (cfg["use_vertex"] or bool(cfg["api_key"]))
        and not is_provider_in_cooldown("gemini")
    )
    if gemini_ready:
        return "gemini"

    groq_cfg = get_groq_config()
    if groq_cfg["api_key"] and not is_provider_in_cooldown("groq"):
        return "groq_fallback"

    or_cfg = get_openrouter_config()
    if or_cfg["api_key"] and not is_provider_in_cooldown("openrouter"):
        return "openrouter_fallback"

    if is_ollama_fallback_enabled():
        return "ollama_fallback"
    return "gemini"


@dataclass
class LLMResult:
    """Normalized LLM generation result with provider provenance."""
    text: str
    provider: str  # "gemini" | "cache" | "groq_fallback" | "openrouter_fallback" | "ollama_fallback"
    grounded: bool = False
    sources: List[Dict[str, str]] = field(default_factory=list)
    model_used: str = ""
    fallback_reason: Optional[str] = None


def _get_genai_client(cfg: Dict[str, Any]):
    """Build or reuse google.genai.Client for either Google AI Studio or Vertex AI."""
    from google import genai

    if cfg["use_vertex"]:
        cache_key = ("vertex", cfg["project"], cfg["location"])
        if cache_key not in _CLIENT_CACHE:
            kwargs: Dict[str, Any] = {"vertexai": True}
            if cfg["project"]:
                kwargs["project"] = cfg["project"]
            if cfg["location"]:
                kwargs["location"] = cfg["location"]
            _CLIENT_CACHE[cache_key] = genai.Client(**kwargs)
        return _CLIENT_CACHE[cache_key]

    api_key = cfg.get("api_key", "")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY / GOOGLE_API_KEY")

    cache_key = ("studio", api_key)
    if cache_key not in _CLIENT_CACHE:
        _CLIENT_CACHE[cache_key] = genai.Client(api_key=api_key)
    return _CLIENT_CACHE[cache_key]


def _extract_grounding_sources(response: Any) -> Tuple[List[Dict[str, str]], bool]:
    """Extract grounding web links from a Gemini GenerateContentResponse."""
    sources: List[Dict[str, str]] = []
    seen_urls: set[str] = set()
    is_grounded = False
    try:
        if response and getattr(response, "candidates", None):
            gm = getattr(response.candidates[0], "grounding_metadata", None)
            chunks = getattr(gm, "grounding_chunks", None) if gm else None
            if chunks:
                for chunk in chunks:
                    web = getattr(chunk, "web", None)
                    if web:
                        uri = getattr(web, "uri", None) or ""
                        title = getattr(web, "title", None) or "F1 Reference"
                        if uri and uri not in seen_urls:
                            seen_urls.add(uri)
                            sources.append({"title": title, "url": uri, "uri": uri})
                            is_grounded = True
    except Exception:
        pass
    return sources, is_grounded


def _trim_for_budget(
    prompt: str,
    system_instruction: Optional[str],
    max_prompt_chars: int = GROQ_MAX_PROMPT_CHARS,
    max_system_chars: int = GROQ_MAX_SYSTEM_CHARS,
) -> Tuple[str, Optional[str]]:
    """Trim prompt & system instruction safely to fit Groq's 8K TPM budget without dropping the question."""
    trimmed_sys = system_instruction
    if trimmed_sys and len(trimmed_sys) > max_system_chars:
        trimmed_sys = trimmed_sys[:max_system_chars] + "\n...[trimmed]"

    trimmed_prompt = prompt or ""
    if len(trimmed_prompt) > max_prompt_chars:
        head_budget = int(max_prompt_chars * 0.65)
        tail_budget = max_prompt_chars - head_budget
        trimmed_prompt = (
            trimmed_prompt[:head_budget]
            + "\n...[context trimmed for TPM budget]...\n"
            + trimmed_prompt[-tail_budget:]
        )
    return trimmed_prompt, trimmed_sys


def _build_chat_messages(
    prompt: str,
    system_instruction: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Construct standard OpenAI/Ollama chat message list."""
    messages: List[Dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    return messages


def _normalize_completions_url(base_url: str) -> str:
    """Resolve OpenAI-compatible /chat/completions endpoint cleanly."""
    clean = base_url.strip().rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    return f"{clean}/chat/completions"


def _extract_openai_message_text(data: Dict[str, Any]) -> str:
    """Extract text content from an OpenAI-compatible chat completions JSON response."""
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        parts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
        content = "".join(parts)
    return str(content or "").strip()


def _extract_openai_stream_delta(frame: Dict[str, Any]) -> str:
    """Extract token delta from an OpenAI-compatible SSE chunk."""
    choices = frame.get("choices") or []
    if not choices:
        return ""
    delta = (choices[0] or {}).get("delta") or {}
    content = delta.get("content")
    if isinstance(content, list):
        parts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
        content = "".join(parts)
    return str(content or "")


def _call_gemini_sync(
    prompt: str,
    *,
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    preferred_thinking_level: Optional[str] = None,
    use_google_search: bool = False,
    cfg: Optional[Dict[str, Any]] = None,
) -> LLMResult:
    """Synchronous Gemini API call supporting optional Google Search Grounding & guarded ThinkingConfig."""
    from google.genai import types

    resolved_cfg = cfg or get_gemini_config()
    if resolved_cfg["provider_mode"] == "ollama":
        raise RuntimeError("LLM_PROVIDER set to ollama")

    client = _get_genai_client(resolved_cfg)
    model_name = model or resolved_cfg["model"]

    t_cfg = build_thinking_config(model_name, preferred_level=preferred_thinking_level)
    cfg_kwargs: Dict[str, Any] = {}
    if system_instruction:
        cfg_kwargs["system_instruction"] = system_instruction
    if use_google_search:
        cfg_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    if t_cfg is not None:
        cfg_kwargs["thinking_config"] = t_cfg

    gen_config = types.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=gen_config,
        )
    except Exception as err:
        if t_cfg is not None and is_unsupported_thinking_error(err):
            fallback_kwargs = {k: v for k, v in cfg_kwargs.items() if k != "thinking_config"}
            fallback_cfg = types.GenerateContentConfig(**fallback_kwargs) if fallback_kwargs else None
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=fallback_cfg,
            )
        else:
            raise

    text = (getattr(response, "text", None) or "").strip()
    sources, is_grounded = _extract_grounding_sources(response) if use_google_search else ([], False)

    return LLMResult(
        text=text,
        provider="gemini",
        grounded=is_grounded,
        sources=sources,
        model_used=model_name,
    )


def _call_openai_compat_sync(
    *,
    provider_label: str,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: Optional[str] = None,
    timeout: float = 30.0,
    extra_headers: Optional[Dict[str, str]] = None,
    max_tokens: int = 512,
) -> LLMResult:
    """Unified synchronous OpenAI-compatible /chat/completions caller for Groq & OpenRouter."""
    url = _normalize_completions_url(base_url)
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    payload: Dict[str, Any] = {
        "model": model,
        "messages": _build_chat_messages(prompt, system_instruction),
        "stream": False,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    resp = httpx.post(
        url,
        headers=headers,
        json=payload,
        timeout=httpx.Timeout(timeout, connect=5.0),
    )
    resp.raise_for_status()
    data = resp.json()
    text = _extract_openai_message_text(data)
    return LLMResult(
        text=text,
        provider=provider_label,
        grounded=False,
        sources=[],
        model_used=model,
    )


def _call_groq_sync(
    prompt: str,
    *,
    system_instruction: Optional[str] = None,
    timeout: float = 30.0,
) -> LLMResult:
    """Synchronous Tier 2 Groq fallback call with 8K TPM prompt trimming."""
    cfg = get_groq_config()
    trimmed_prompt, trimmed_sys = _trim_for_budget(prompt, system_instruction)
    return _call_openai_compat_sync(
        provider_label="groq_fallback",
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        prompt=trimmed_prompt,
        system_instruction=trimmed_sys,
        timeout=timeout,
        max_tokens=512,
    )


def _call_openrouter_sync(
    prompt: str,
    *,
    system_instruction: Optional[str] = None,
    timeout: float = 35.0,
) -> LLMResult:
    """Synchronous Tier 3 OpenRouter fallback call with X-Title & optional HTTP-Referer headers."""
    cfg = get_openrouter_config()
    extra_headers: Dict[str, str] = {"X-Title": "PitWall AI"}
    if cfg.get("http_referer"):
        extra_headers["HTTP-Referer"] = cfg["http_referer"]
    return _call_openai_compat_sync(
        provider_label="openrouter_fallback",
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        prompt=prompt,
        system_instruction=system_instruction,
        timeout=timeout,
        extra_headers=extra_headers,
        max_tokens=512,
    )


def _call_ollama_sync(
    prompt: str,
    *,
    system_instruction: Optional[str] = None,
    timeout: float = 150.0,
) -> LLMResult:
    """Synchronous Tier 4 local Ollama /api/chat call with capped CPU context and output tokens."""
    chat_url = get_ollama_chat_url()
    ollama_model = get_ollama_model()

    resp = httpx.post(
        chat_url,
        json={
            "model": ollama_model,
            "messages": _build_chat_messages(prompt, system_instruction),
            "stream": False,
            "think": False,
            "keep_alive": "15m",
            "options": dict(OLLAMA_DEFAULT_OPTIONS),
        },
        timeout=httpx.Timeout(timeout, connect=5.0),
    )
    resp.raise_for_status()
    data = resp.json()
    content = (data.get("message", {}) or {}).get("content", "") or data.get("response", "") or ""
    return LLMResult(
        text=content.strip(),
        provider="ollama_fallback",
        grounded=False,
        sources=[],
        model_used=ollama_model,
    )


def _attempt_cloud_sync_tier(
    *,
    provider_key: str,
    provider_label: str,
    model_name: str,
    call_fn: Any,
) -> Tuple[Optional[LLMResult], Optional[str]]:
    """Execute one sync cloud tier with cooldown protection and sanitized error logging."""
    if is_provider_in_cooldown(provider_key):
        logger.info("%s 429 cooldown active; skipping redundant call.", provider_key)
        return None, f"{provider_key} 429 cooldown active"

    t0 = time.perf_counter()
    try:
        res = call_fn()
        if res and res.text:
            return res, None
        reason = f"Empty {provider_key} response"
        logger.warning("%s returned empty text; advancing failover cascade.", provider_key)
        return None, reason
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        if provider_key == "gemini":
            record_gemini_failover()
        if _is_rate_limit_error(exc):
            record_provider_429_cooldown(provider_key, PROVIDER_429_COOLDOWN_SECONDS)
        logger.warning(
            "Provider '%s' (%s) failed after %.1fs [%s]: %s",
            provider_label,
            model_name,
            elapsed,
            type(exc).__name__,
            exc,
        )
        return None, str(exc)


def generate_with_failover(
    prompt: str,
    *,
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    preferred_thinking_level: Optional[str] = None,
    use_google_search: bool = False,
    ollama_timeout: float = 150.0,
) -> LLMResult:
    """
    Execute 4-tier cascading generation:
      1) Gemini (primary, supports google_search grounding) -> "gemini"
      2) Groq (OpenAI-compat, 30s timeout, trimmed 8K TPM context) -> "groq_fallback"
      3) OpenRouter (OpenAI-compat, 35s timeout) -> "openrouter_fallback"
      4) Local Ollama (qwen3.5:4b, 150s timeout) ONLY if ENABLE_OLLAMA_FALLBACK resolves True -> "ollama_fallback"
    """
    cfg = get_gemini_config()
    last_reason: Optional[str] = None

    # Tier 1: Gemini
    if cfg["provider_mode"] != "ollama":
        res, reason = _attempt_cloud_sync_tier(
            provider_key="gemini",
            provider_label="gemini",
            model_name=model or cfg["model"],
            call_fn=lambda: _call_gemini_sync(
                prompt,
                system_instruction=system_instruction,
                model=model,
                preferred_thinking_level=preferred_thinking_level,
                use_google_search=use_google_search,
                cfg=cfg,
            ),
        )
        if res is not None:
            return res
        last_reason = reason
    else:
        last_reason = "LLM_PROVIDER configured as ollama"

    # Tier 2: Groq
    groq_cfg = get_groq_config()
    if cfg["provider_mode"] != "ollama" and groq_cfg["api_key"]:
        res, reason = _attempt_cloud_sync_tier(
            provider_key="groq",
            provider_label="groq_fallback",
            model_name=groq_cfg["model"],
            call_fn=lambda: _call_groq_sync(
                prompt,
                system_instruction=system_instruction,
                timeout=30.0,
            ),
        )
        if res is not None:
            res.fallback_reason = last_reason
            return res
        last_reason = reason

    # Tier 3: OpenRouter
    or_cfg = get_openrouter_config()
    if cfg["provider_mode"] != "ollama" and or_cfg["api_key"]:
        res, reason = _attempt_cloud_sync_tier(
            provider_key="openrouter",
            provider_label="openrouter_fallback",
            model_name=or_cfg["model"],
            call_fn=lambda: _call_openrouter_sync(
                prompt,
                system_instruction=system_instruction,
                timeout=35.0,
            ),
        )
        if res is not None:
            res.fallback_reason = last_reason
            return res
        last_reason = reason

    # Tier 4: Local Ollama (gated cleanly for APP_ENV=production)
    if not is_ollama_fallback_enabled():
        logger.info("Local Ollama fallback disabled (APP_ENV=production / ENABLE_OLLAMA_FALLBACK=False); skipping 127.0.0.1 probe.")
        return LLMResult(
            text="",
            provider="openrouter_fallback" if or_cfg["api_key"] else ("groq_fallback" if groq_cfg["api_key"] else "gemini"),
            grounded=False,
            sources=[],
            model_used="",
            fallback_reason=last_reason or "All configured cloud LLM providers unavailable in production mode",
        )

    t_ollama = time.perf_counter()
    chat_url = get_ollama_chat_url()
    try:
        ollama_res = _call_ollama_sync(
            prompt,
            system_instruction=system_instruction,
            timeout=ollama_timeout,
        )
        ollama_res.fallback_reason = last_reason
        return ollama_res
    except Exception as ollama_exc:
        elapsed = time.perf_counter() - t_ollama
        logger.warning(
            "Local Ollama fallback unavailable (%s) after %.1fs [%s]: %s",
            chat_url,
            elapsed,
            type(ollama_exc).__name__,
            ollama_exc,
        )
        return LLMResult(
            text="",
            provider="ollama_fallback",
            grounded=False,
            sources=[],
            model_used=get_ollama_model(),
            fallback_reason="All enabled LLM providers unavailable",
        )


async def _stream_openai_compat(
    *,
    provider_key: str,
    provider_label: str,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: Optional[str] = None,
    timeout: float = 30.0,
    extra_headers: Optional[Dict[str, str]] = None,
    max_tokens: int = 512,
    provider_state: Optional[Dict[str, str]] = None,
) -> AsyncGenerator[str, None]:
    """Stream tokens from an OpenAI-compatible SSE /chat/completions endpoint."""
    url = _normalize_completions_url(base_url)
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    payload: Dict[str, Any] = {
        "model": model,
        "messages": _build_chat_messages(prompt, system_instruction),
        "stream": True,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }

    state = provider_state if provider_state is not None else {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=5.0)) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for raw_line in resp.aiter_lines():
                line = raw_line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    frame = json.loads(data_str)
                except Exception:
                    continue
                delta = _extract_openai_stream_delta(frame)
                if delta:
                    state["provider"] = provider_label
                    yield delta


async def stream_with_failover(
    prompt: str,
    *,
    system_instruction: Optional[str] = None,
    model: Optional[str] = None,
    fallback_text: str = "",
    provider_state: Optional[Dict[str, str]] = None,
    ollama_timeout: float = 150.0,
) -> AsyncGenerator[str, None]:
    """
    Async 4-tier cascading streaming helper:
      1) Gemini client.aio streaming -> "gemini"
      2) Groq OpenAI-compatible SSE (timeout=30.0, trimmed context) -> "groq_fallback"
      3) OpenRouter OpenAI-compatible SSE (timeout=35.0) -> "openrouter_fallback"
      4) Local Ollama /api/chat NDJSON (timeout=150.0, gated by ENABLE_OLLAMA_FALLBACK) -> "ollama_fallback"
      5) Deterministic pit-wall radio text if all enabled tiers fail.
    """
    from google.genai import types

    cfg = get_gemini_config()
    model_name = model or cfg["model"]
    state = provider_state if provider_state is not None else {}

    # Tier 1: Gemini async stream
    if cfg["provider_mode"] != "ollama" and not is_provider_in_cooldown("gemini"):
        try:
            client = _get_genai_client(cfg)
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
            t_cfg = build_thinking_config(model_name)
            cfg_kwargs: Dict[str, Any] = {}
            if system_instruction:
                cfg_kwargs["system_instruction"] = system_instruction
            if t_cfg is not None:
                cfg_kwargs["thinking_config"] = t_cfg
            gen_cfg = types.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None

            try:
                stream = await client.aio.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=gen_cfg,
                )
            except Exception as think_err:
                if t_cfg is not None and is_unsupported_thinking_error(think_err):
                    fallback_kwargs = {k: v for k, v in cfg_kwargs.items() if k != "thinking_config"}
                    fallback_cfg = types.GenerateContentConfig(**fallback_kwargs) if fallback_kwargs else None
                    stream = await client.aio.models.generate_content_stream(
                        model=model_name,
                        contents=contents,
                        config=fallback_cfg,
                    )
                else:
                    raise

            chunk_emitted = False
            async for chunk_resp in stream:
                txt = getattr(chunk_resp, "text", None)
                if txt:
                    chunk_emitted = True
                    state["provider"] = "gemini"
                    yield txt
            if chunk_emitted:
                return
        except Exception as exc:
            record_gemini_failover()
            if _is_rate_limit_error(exc):
                record_provider_429_cooldown("gemini", PROVIDER_429_COOLDOWN_SECONDS)
            logger.warning("Gemini streaming failed (%s); failing over: %s", model_name, exc)
    elif is_provider_in_cooldown("gemini"):
        logger.info("Gemini 429 cooldown active; skipping Gemini streaming.")

    # Tier 2: Groq async SSE stream
    groq_cfg = get_groq_config()
    if cfg["provider_mode"] != "ollama" and groq_cfg["api_key"] and not is_provider_in_cooldown("groq"):
        t_groq = time.perf_counter()
        trimmed_prompt, trimmed_sys = _trim_for_budget(prompt, system_instruction)
        chunk_emitted = False
        try:
            async for delta in _stream_openai_compat(
                provider_key="groq",
                provider_label="groq_fallback",
                base_url=groq_cfg["base_url"],
                api_key=groq_cfg["api_key"],
                model=groq_cfg["model"],
                prompt=trimmed_prompt,
                system_instruction=trimmed_sys,
                timeout=30.0,
                max_tokens=512,
                provider_state=state,
            ):
                chunk_emitted = True
                yield delta
            if chunk_emitted:
                return
        except Exception as exc:
            elapsed = time.perf_counter() - t_groq
            if _is_rate_limit_error(exc):
                record_provider_429_cooldown("groq", PROVIDER_429_COOLDOWN_SECONDS)
            logger.warning(
                "Groq streaming failed (%s) after %.1fs [%s]: %s",
                groq_cfg["model"],
                elapsed,
                type(exc).__name__,
                exc,
            )
            if chunk_emitted:
                return

    # Tier 3: OpenRouter async SSE stream
    or_cfg = get_openrouter_config()
    if cfg["provider_mode"] != "ollama" and or_cfg["api_key"] and not is_provider_in_cooldown("openrouter"):
        t_or = time.perf_counter()
        or_headers: Dict[str, str] = {"X-Title": "PitWall AI"}
        if or_cfg.get("http_referer"):
            or_headers["HTTP-Referer"] = or_cfg["http_referer"]
        chunk_emitted = False
        try:
            async for delta in _stream_openai_compat(
                provider_key="openrouter",
                provider_label="openrouter_fallback",
                base_url=or_cfg["base_url"],
                api_key=or_cfg["api_key"],
                model=or_cfg["model"],
                prompt=prompt,
                system_instruction=system_instruction,
                timeout=35.0,
                extra_headers=or_headers,
                max_tokens=512,
                provider_state=state,
            ):
                chunk_emitted = True
                yield delta
            if chunk_emitted:
                return
        except Exception as exc:
            elapsed = time.perf_counter() - t_or
            if _is_rate_limit_error(exc):
                record_provider_429_cooldown("openrouter", PROVIDER_429_COOLDOWN_SECONDS)
            logger.warning(
                "OpenRouter streaming failed (%s) after %.1fs [%s]: %s",
                or_cfg["model"],
                elapsed,
                type(exc).__name__,
                exc,
            )
            if chunk_emitted:
                return

    # Tier 4: Local Ollama /api/chat streaming fallback (gated by APP_ENV / ENABLE_OLLAMA_FALLBACK)
    if is_ollama_fallback_enabled():
        t_ollama = time.perf_counter()
        chat_url = get_ollama_chat_url()
        try:
            ollama_model = get_ollama_model()
            state["provider"] = "ollama_fallback"
            chunk_emitted = False
            async with httpx.AsyncClient(timeout=httpx.Timeout(ollama_timeout, connect=5.0)) as client:
                async with client.stream(
                    "POST",
                    chat_url,
                    json={
                        "model": ollama_model,
                        "messages": _build_chat_messages(prompt, system_instruction),
                        "stream": True,
                        "think": False,
                        "keep_alive": "15m",
                        "options": dict(OLLAMA_DEFAULT_OPTIONS),
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            frame = json.loads(line)
                        except Exception:
                            continue
                        delta = (frame.get("message", {}) or {}).get("content", "") or frame.get("response", "")
                        if delta:
                            chunk_emitted = True
                            yield delta
            if chunk_emitted:
                return
        except Exception as ollama_exc:
            elapsed = time.perf_counter() - t_ollama
            logger.warning(
                "Local Ollama fallback unavailable (%s) after %.1fs [%s]: %s",
                chat_url,
                elapsed,
                type(ollama_exc).__name__,
                ollama_exc,
            )
    else:
        logger.info("Local Ollama streaming fallback disabled (APP_ENV=production); skipping 127.0.0.1 probe.")

    # Deterministic pit-wall fallback text if all enabled tiers fail
    state.setdefault(
        "provider",
        "ollama_fallback" if is_ollama_fallback_enabled() else "gemini",
    )
    if fallback_text:
        words = fallback_text.split(" ")
        for i in range(0, len(words), 3):
            chunk = " ".join(words[i : i + 3]) + (" " if i + 3 < len(words) else "")
            yield chunk
            await asyncio.sleep(0.01)
