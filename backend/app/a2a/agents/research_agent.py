"""
Research Specialist Agent for PitWall AI (A2A).
Handles:
- Off-dataset Formula 1 questions (regulations, steward decisions, driver quotes, weather, technical updates)
- Grounded web search via Google Gemini google_search grounding (when GOOGLE_API_KEY available)
- Graceful offline fallback in local Ollama mode
- Web verification of unknown corner nicknames -> turn numbers, persisting to learned_aliases.json
- Storing research sources & cards in ArtifactStore with dataset_id
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional

from google.adk.agents.llm_agent import LlmAgent
from a2a.types import AgentCard, AgentSkill, AgentInterface

from backend.app.config import settings
from backend.app.llm import generate_with_failover, get_gemini_config
from backend.app.a2a.artifact_store import get_artifact_store
from backend.app.data.circuit_corners import get_circuit_corner_engine

logger = logging.getLogger("pitwall.a2a.research")


def sanitize_bullets(raw_items: Any) -> List[str]:
    """
    Normalize a list of bullet strings or newline-separated lines:
    splits embedded newlines, strips repeated '-', '*', '•', or '1.' prefixes,
    and drops empty/punctuation-only rows so stray blank '- ' lines never render.
    """
    if not isinstance(raw_items, (list, tuple)):
        return []
    cleaned: List[str] = []
    for item in raw_items:
        if not isinstance(item, str):
            continue
        for subline in item.splitlines():
            s = subline.replace("\u200b", "").replace("\ufeff", "").strip()
            while s:
                next_s = re.sub(r"^(?:[-•*–—]+|\d+[.)]+)\s*", "", s).strip()
                if next_s == s:
                    break
                s = next_s
            if not s or re.fullmatch(r"[-•*–—.\s]+", s):
                continue
            cleaned.append(s)
    return cleaned


def sanitize_summary_text(text: str) -> str:
    """Remove standalone empty bullet lines ('- ', '* ') from research summary text."""
    lines = [
        line for line in (text or "").splitlines()
        if not re.fullmatch(r"\s*[-•*–—]+\s*", line)
    ]
    return "\n".join(lines).strip()


def _extract_clean_bullets(text: str) -> List[str]:
    """
    Extract bullet takeaways cleanly from markdown or plain prose, stripping leading list markers
    and dropping any empty or whitespace-only entries (prevents blank '- ' bullets).
    """
    candidate_lines: List[str] = []
    for raw_line in (text or "").splitlines():
        s = raw_line.replace("\u200b", "").replace("\ufeff", "").strip()
        if not s:
            continue
        if s.startswith(("-", "•", "*", "–", "—")) or re.match(r"^\d+[\.\)]\s+", s):
            candidate_lines.append(s)

    bullets = sanitize_bullets(candidate_lines)
    if not bullets and (text or "").strip():
        clean_prose = sanitize_summary_text(text)
        sentences = [seg.strip() for seg in re.split(r"(?<=[.!?])\s+", clean_prose) if seg.strip()]
        bullets = sanitize_bullets([s for s in sentences[:3] if len(s) > 3])

    return bullets


class ResearchAgent:
    """Specialist agent for web intelligence and corner nickname discovery."""

    def __init__(self, name: str = "research_agent", cache_dir: Optional[Path] = None):
        self.name = name
        self.artifact_store = get_artifact_store()
        self.corner_engine = get_circuit_corner_engine()
        self.cache_dir = Path(cache_dir or getattr(settings, "RESEARCH_CACHE_DIR", Path("./data/research_cache")))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cfg = get_gemini_config()
        self.api_key = cfg.get("api_key", "")
        self.has_gemini = bool(self.api_key or cfg.get("use_vertex"))
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> LlmAgent:
        """Create ADK LlmAgent wrapper."""
        tools = [self.research_topic, self.resolve_and_learn_corner]
        return LlmAgent(
            name=self.name,
            model=settings.GEMINI_MODEL if self.has_gemini else f"ollama_chat/{settings.OLLAMA_MODEL}",
            instruction=(
                "You are the PitWall AI Research Engineer. Search live web sources for off-dataset F1 inquiries "
                "such as regulations, driver quotes, weather forecasts, technical upgrades, and track corner designations. "
                "Always provide source citations."
            ),
            tools=tools,
        )

    def _cache_path_for_query(self, query: str) -> Path:
        norm = re.sub(r"\s+", " ", query.strip().lower())
        key = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.json"

    def _read_research_cache(self, query: str) -> Optional[Dict[str, Any]]:
        path = self._cache_path_for_query(query)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("grounded") is True and data.get("sources"):
                return data
        except Exception as e:
            logger.warning(f"Failed reading research cache {path}: {e}")
        return None

    def _write_research_cache(self, query: str, payload: Dict[str, Any]) -> None:
        if not payload.get("grounded") or not payload.get("sources"):
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_path_for_query(query)
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            tmp.replace(path)
        except Exception as e:
            logger.warning(f"Failed writing research cache {path}: {e}")

    def research_topic(self, query: str) -> Dict[str, Any]:
        """
        Execute web research on an F1 topic in strict priority order:
        1) Persistent Disk Cache (./data/research_cache/) for previously grounded queries (0 API calls)
        2) Gemini + Google Search Grounding (saves grounded results to disk cache)
        3) Local Ollama Fallback (qwen3.5:4b) on 429 / network error (grounded=False, provider='ollama_fallback')
        4) Clean fallback notice if Ollama is also unreachable (zero raw tracebacks/JSON leaks).
        """
        t_start = time.perf_counter()

        sources: List[Dict[str, str]] = []
        findings: List[str] = []
        summary = ""
        is_grounded = False
        provider = "gemini"

        # Step 1: Persistent Disk Cache (0 API quota spent)
        cached = self._read_research_cache(query)
        if cached:
            summary = sanitize_summary_text(cached.get("summary", ""))
            findings = sanitize_bullets(cached.get("findings", []))
            if not findings:
                findings = _extract_clean_bullets(summary)
            sources = cached.get("sources", [])
            is_grounded = True
            provider = "cache"
        else:
            # Step 2 -> Step 3 -> Step 4 via Unified Failover Client
            prompt = (
                f"Formula 1 research question: {query}\n"
                "Reply concisely (max 120 words): 1-2 short summary sentences followed by "
                "2-3 brief factual bullet points formatted as '- fact'."
            )
            llm_res = generate_with_failover(
                prompt,
                use_google_search=True,
                ollama_timeout=150.0,
            )

            if llm_res.provider == "gemini" and llm_res.text:
                summary = sanitize_summary_text(llm_res.text)
                sources = llm_res.sources
                is_grounded = bool(llm_res.grounded and sources)
                findings = _extract_clean_bullets(summary)
                provider = "gemini"
                if is_grounded and sources:
                    self._write_research_cache(
                        query,
                        {
                            "query": query,
                            "summary": summary,
                            "findings": findings,
                            "sources": sources,
                            "grounded": True,
                            "cached_at": time.time(),
                        },
                    )
            elif llm_res.text:
                # Step 3: Local Ollama Fallback succeeded
                summary = sanitize_summary_text(llm_res.text)
                findings = _extract_clean_bullets(summary)
                sources = []
                is_grounded = False
                provider = "ollama_fallback"
            else:
                # Step 4: Both Gemini and local Ollama are unreachable -> clean user notice
                summary = (
                    f"Live web search and the local fallback model are temporarily unavailable for '{query}'. "
                    f"Please retry shortly or ensure local Ollama is running."
                )
                findings = [
                    "Live web grounding is temporarily rate-limited or offline.",
                    "Local Ollama fallback model could not be reached at this moment.",
                ]
                sources = []
                is_grounded = False
                provider = "ollama_fallback"

        exec_time = round((time.perf_counter() - t_start) * 1000, 2)

        # Store research payload in ArtifactStore
        dataset_metadata = {
            "domain": "research",
            "query": query,
            "sources_count": len(sources),
            "grounded": is_grounded,
            "provider": provider,
        }
        dataset_id = self.artifact_store.put(
            data={
                "query": query,
                "summary": summary,
                "findings": findings,
                "sources": sources,
                "grounded": is_grounded,
                "provider": provider,
            },
            metadata=dataset_metadata,
            ttl_seconds=3600,
        )

        web_card = {
            "topic": query,
            "summary": summary,
            "key_findings": findings,
            "sources": sources,
            "grounded": is_grounded,
            "provider": provider,
            "confidence": 0.95 if is_grounded else 0.70,
        }

        return {
            "success": True,
            "domain": "research",
            "dataset_id": dataset_id,
            "summary": summary,
            "web_card": web_card,
            "sources": sources,
            "grounded": is_grounded,
            "provider": provider,
            "execution_time_ms": exec_time,
            "trace": {
                "data_domain": "research",
                "query": query,
                "sources_count": len(sources),
                "provider": provider,
                "grounding_provider": "gemini_google_search" if is_grounded else ("cache" if provider == "cache" else "ollama_fallback"),
            },
        }

    def resolve_and_learn_corner(self, circuit: str, corner_query: str) -> Dict[str, Any]:
        """
        Research an unknown corner nickname, determine its official turn number,
        verify against MultiViewer geometry, and save to learned_aliases.json.
        """
        circuit_info = self.corner_engine.get_circuit_info(circuit)
        circuit_slug = circuit_info["slug"] if circuit_info else circuit.lower().replace(" ", "_")
        circuit_key = circuit_info["key"] if circuit_info else 0

        # Ask targeted query
        search_prompt = (
            f"What official Turn number is the corner called '{corner_query}' at the Formula 1 circuit "
            f"'{circuit_info['name'] if circuit_info else circuit}'? Reply with just the number or 'Turn X'."
        )
        research_res = self.research_topic(search_prompt)
        text = research_res.get("summary", "")

        turn_match = re.search(r"(?:turn|corner|curva|t)\s*(\d+)", text, re.IGNORECASE)
        if not turn_match:
            turn_match = re.search(r"\b(\d{1,2})\b", text)

        if turn_match:
            candidate_turn = int(turn_match.group(1))
            # Verify candidate turn against MultiViewer circuit geometry
            coords = self.corner_engine.get_corner_coordinates(circuit_key, candidate_turn)
            if coords:
                # Successfully verified! Learn alias
                self.corner_engine.learn_alias(
                    circuit_slug=circuit_slug,
                    nickname=corner_query,
                    turn_number=candidate_turn,
                    distance_m=float(coords.get("length", 0.0) / 10.0) if coords.get("length") else 0.0,
                    source="web_verified",
                )
                return {
                    "success": True,
                    "verified": True,
                    "circuit": circuit_slug,
                    "corner_nickname": corner_query,
                    "turn_number": candidate_turn,
                    "coordinates": coords,
                    "message": f"Successfully verified '{corner_query}' as Turn {candidate_turn} at {circuit_slug} and updated learned aliases.",
                }

        return {
            "success": False,
            "verified": False,
            "circuit": circuit_slug,
            "corner_nickname": corner_query,
            "message": f"Could not definitively verify Turn number for corner '{corner_query}' at {circuit_slug}.",
        }

    @classmethod
    def get_agent_card(cls, base_url: str = "http://localhost:8000/a2a/research") -> AgentCard:
        """Construct standard A2A AgentCard for ResearchAgent."""
        return AgentCard(
            name="research_agent",
            description="Formula 1 Web Research & Grounding Agent powered by Google Gemini Search Grounding.",
            version="1.0.0",
            supported_interfaces=[
                AgentInterface(url=base_url, protocol_binding="HTTP_JSON", protocol_version="1.0")
            ],
            skills=[
                AgentSkill(
                    id="research_topic",
                    name="research_topic",
                    description="Performs grounded web search for off-dataset F1 inquiries (regulations, driver quotes, weather, technical upgrades).",
                    tags=["research", "web", "regulations", "news"],
                ),
                AgentSkill(
                    id="resolve_and_learn_corner",
                    name="resolve_and_learn_corner",
                    description="Researches and verifies an unknown track corner nickname against MultiViewer geometry.",
                    tags=["circuit", "corners", "verification"],
                ),
            ],
        )


_research_agent_instance: Optional[ResearchAgent] = None


def get_research_agent() -> ResearchAgent:
    """Get singleton ResearchAgent."""
    global _research_agent_instance
    if _research_agent_instance is None:
        _research_agent_instance = ResearchAgent()
    return _research_agent_instance
