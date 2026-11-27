"""
Unified Gemini -> Local Ollama Runtime Failover Helper for PitWall AI.
Used across PitWallEngineer, HistoricalSQLAgent, and ResearchAgent.

- Purely env-driven Gemini config:
  * GEMINI_API_KEY / GOOGLE_API_KEY
  * GEMINI_MODEL
  * Optional Vertex AI: GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION
- Automatic failover to local Ollama (OLLAMA_BASE_URL, OLLAMA_MODEL) on ANY runtime Gemini failure
  (429 RESOURCE_EXHAUSTED, 503, timeouts, missing key, etc.).
- Full Gemini exceptions are logged server-side via logger.warning and never leaked to UI text.
- Exposes explicit provider attribution: "gemini" | "ollama_fallback" | "cache".
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
_GEMINI_429_COOLDOWN_UNTIL: float = 0.0
GEMINI_429_COOLDOWN_SECONDS: float = 60.0
OLLAMA_DEFAULT_OPTIONS: Dict[str, Any] = {
    "num_ctx": 1024,
    "num_predict": 180,
    "temperature": 0.3,
}


def record_gemini_failover() -> None:
    """Record timestamp of most recent runtime Gemini -> Ollama failover."""
    global _LAST_GEMINI_FAILOVER_AT
    _LAST_GEMINI_FAILOVER_AT = time.time()


def record_gemini_429_cooldown(seconds: float = GEMINI_429_COOLDOWN_SECONDS) -> None:
    """Enter cooldown window after 429 RESOURCE_EXHAUSTED so repeated Gemini quota errors are skipped."""
    global _GEMINI_429_COOLDOWN_UNTIL
    _GEMINI_429_COOLDOWN_UNTIL = time.time() + seconds


def reset_gemini_cooldown() -> None:
    """Reset Gemini cooldown & failover state (used in tests and recovery)."""
    global _LAST_GEMINI_FAILOVER_AT, _GEMINI_429_COOLDOWN_UNTIL
    _LAST_GEMINI_FAILOVER_AT = 0.0
    _GEMINI_429_COOLDOWN_UNTIL = 0.0


def is_gemini_in_cooldown() -> bool:
    """Return True if Gemini is currently in a 429 rate-limit cooldown window."""
    return _GEMINI_429_COOLDOWN_UNTIL > 0 and time.time() < _GEMINI_429_COOLDOWN_UNTIL


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detect HTTP 429 / RESOURCE_EXHAUSTED quota errors."""
    msg = str(exc).lower()
    return "429" in msg or "resource_exhausted" in msg or "rate limit" in msg or "quota" in msg


def get_active_provider_hint() -> str:
    """Return 'ollama_fallback' when Ollama mode is active or Gemini is in cooldown / recently failed over."""
    cfg = get_gemini_config()
    if cfg["provider_mode"] == "ollama":
        return "ollama_fallback"
    if not cfg["use_vertex"] and not cfg["api_key"]:
        return "ollama_fallback"
    if is_gemini_in_cooldown():
        return "ollama_fallback"
    if _LAST_GEMINI_FAILOVER_AT > 0 and (time.time() - _LAST_GEMINI_FAILOVER_AT) < 60.0:
        return "ollama_fallback"
    return "gemini"


@dataclass
class LLMResult:
    """Normalized LLM generation result with provider provenance."""
    text: str
    provider: str  # "gemini" | "ollama_fallback" | "cache"
    grounded: bool = False
    sources: List[Dict[str, str]] = field(default_factory=list)
    model_used: str = ""
    fallback_reason: Optional[str] = None


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


def _call_ollama_sync(
    prompt: str,
    *,
    system_instruction: Optional[str] = None,
    timeout: float = 150.0,
) -> LLMResult:
    """Synchronous local Ollama /api/chat call with capped CPU context and output tokens."""
    chat_url = get_ollama_chat_url()
    ollama_model = get_ollama_model()

    messages: List[Dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    resp = httpx.post(
        chat_url,
        json={
            "model": ollama_model,
            "messages": messages,
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
    Attempt Gemini generation first (unless in 60s 429 cooldown); on ANY runtime failure
    (429 RESOURCE_EXHAUSTED, 503 UNAVAILABLE, timeout, network error, missing key),
    log server-side via logger.warning and fail over cleanly to local Ollama.
    """
    cfg = get_gemini_config()
    gemini_error_str: Optional[str] = None

    if cfg["provider_mode"] != "ollama" and not is_gemini_in_cooldown():
        try:
            res = _call_gemini_sync(
                prompt,
                system_instruction=system_instruction,
                model=model,
                preferred_thinking_level=preferred_thinking_level,
                use_google_search=use_google_search,
                cfg=cfg,
            )
            if res.text:
                return res
            gemini_error_str = "Empty Gemini response"
            logger.warning("Gemini returned empty text; failing over to local Ollama.")
        except Exception as exc:
            gemini_error_str = str(exc)
            record_gemini_failover()
            if _is_rate_limit_error(exc):
                record_gemini_429_cooldown(GEMINI_429_COOLDOWN_SECONDS)
            logger.warning(
                "Gemini call failed (%s); failing over cleanly to local Ollama (%s): %s",
                model or cfg["model"],
                get_ollama_model(),
                exc,
            )
    elif is_gemini_in_cooldown():
        gemini_error_str = "Gemini 429 cooldown active"
        logger.info("Gemini 429 cooldown active; skipping redundant Gemini call and routing directly to local Ollama.")
    else:
        gemini_error_str = "LLM_PROVIDER configured as ollama"

    t_ollama = time.perf_counter()
    chat_url = get_ollama_chat_url()
    try:
        ollama_res = _call_ollama_sync(
            prompt,
            system_instruction=system_instruction,
            timeout=ollama_timeout,
        )
        ollama_res.fallback_reason = gemini_error_str
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
            fallback_reason="Gemini and local Ollama unavailable",
        )


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
    Async streaming helper: tries Gemini client.aio streaming first (unless in 60s 429 cooldown),
    failing over seamlessly to local Ollama /api/chat streaming on any Gemini error,
    and finally deterministic pit-wall radio text if Ollama is also unreachable.
    """
    from google.genai import types

    cfg = get_gemini_config()
    model_name = model or cfg["model"]
    state = provider_state if provider_state is not None else {}

    if cfg["provider_mode"] != "ollama" and not is_gemini_in_cooldown():
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
                record_gemini_429_cooldown(GEMINI_429_COOLDOWN_SECONDS)
            logger.warning("Gemini streaming failed (%s); failing over to local Ollama: %s", model_name, exc)
    elif is_gemini_in_cooldown():
        logger.info("Gemini 429 cooldown active; streaming commentary directly from local Ollama.")

    # Local Ollama /api/chat streaming fallback
    t_ollama = time.perf_counter()
    chat_url = get_ollama_chat_url()
    try:
        ollama_model = get_ollama_model()
        messages: List[Dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        state["provider"] = "ollama_fallback"
        chunk_emitted = False
        async with httpx.AsyncClient(timeout=httpx.Timeout(ollama_timeout, connect=5.0)) as client:
            async with client.stream(
                "POST",
                chat_url,
                json={
                    "model": ollama_model,
                    "messages": messages,
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

    # Deterministic pit-wall fallback text if both Gemini and Ollama are offline
    state.setdefault("provider", "ollama_fallback")
    if fallback_text:
        words = fallback_text.split(" ")
        for i in range(0, len(words), 3):
            chunk = " ".join(words[i : i + 3]) + (" " if i + 3 < len(words) else "")
            yield chunk
            await asyncio.sleep(0.01)
