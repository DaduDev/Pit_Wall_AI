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

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from google.adk.agents.llm_agent import LlmAgent
from a2a.types import AgentCard, AgentSkill, AgentInterface

from backend.app.config import settings
from backend.app.a2a.artifact_store import get_artifact_store
from backend.app.data.circuit_corners import get_circuit_corner_engine

logger = logging.getLogger("pitwall.a2a.research")


class ResearchAgent:
    """Specialist agent for web intelligence and corner nickname discovery."""

    def __init__(self, name: str = "research_agent"):
        self.name = name
        self.artifact_store = get_artifact_store()
        self.corner_engine = get_circuit_corner_engine()
        self.api_key = (
            os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or getattr(settings, "GOOGLE_API_KEY", "")
            or getattr(settings, "GEMINI_API_KEY", "")
        )
        if not self.api_key:
            try:
                from dotenv import dotenv_values
                env_vals = dotenv_values(".env")
                self.api_key = env_vals.get("GOOGLE_API_KEY") or env_vals.get("GEMINI_API_KEY") or ""
            except Exception:
                pass
        self.has_gemini = bool(self.api_key)
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> LlmAgent:
        """Create ADK LlmAgent wrapper."""
        tools = [self.research_topic, self.resolve_and_learn_corner]
        return LlmAgent(
            name=self.name,
            model="gemini-3.8-flash" if self.has_gemini else "ollama_chat/qwen3.5:4b",
            instruction=(
                "You are the PitWall AI Research Engineer. Search live web sources for off-dataset F1 inquiries "
                "such as regulations, driver quotes, weather forecasts, technical upgrades, and track corner designations. "
                "Always provide source citations."
            ),
            tools=tools,
        )

    def research_topic(self, query: str) -> Dict[str, Any]:
        """
        Execute web research on an F1 topic.
        If Gemini grounding is available, runs grounded search; otherwise uses structured offline fallback.
        """
        t_start = time.perf_counter()

        sources: List[Dict[str, str]] = []
        findings: List[str] = []
        summary = ""
        is_grounded = False

        if not self.has_gemini:
            # Offline / local Ollama mode fallback
            summary = (
                f"Web search is unavailable in offline/local LLM mode. "
                f"General domain context for '{query}': Formula 1 regulations, historical statistics, and race data "
                f"are accessible via historical DuckDB views and cached telemetry."
            )
            findings = [
                "Live web grounding requires active GOOGLE_API_KEY or GEMINI_API_KEY.",
                "Offline dataset contains all official F1 race results (1950–2024+) and car telemetry (2023+).",
            ]
            sources = [{"title": "PitWall AI Offline Knowledge", "url": "local://pitwall-db", "uri": "local://pitwall-db"}]
        else:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key)
                prompt = (
                    f"You are a Formula 1 research specialist. Answer this question concisely with exact facts: {query}\n"
                    f"Cite specific race events, driver quotes, regulations, or dates where applicable."
                )

                # Generate content with google search grounding tool
                # Attempt primary models, falling back to grounding-compatible Flash/preview models
                response = None
                models_to_try = [
                    "gemini-3.8-flash",
                    "gemini-3.5-flash-lite",
                    "gemini-3.5-flash",
                    "gemini-flash-latest",
                    "gemini-robotics-er-2-preview",
                ]
                last_err = None

                for model_candidate in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=model_candidate,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                tools=[types.Tool(google_search=types.GoogleSearch())],
                            ),
                        )
                        if response:
                            break
                    except Exception as try_err:
                        last_err = try_err
                        logger.warning(f"Search grounding attempt with {model_candidate} failed: {try_err}")

                if response is None:
                    raise last_err or RuntimeError("No response returned from Gemini models")

                summary = response.text or "No text generated."

                # Extract grounding metadata sources if returned
                if response.candidates and response.candidates[0].grounding_metadata:
                    gm = response.candidates[0].grounding_metadata
                    if gm.grounding_chunks:
                        for chunk in gm.grounding_chunks:
                            if chunk.web:
                                link_url = chunk.web.uri or ""
                                sources.append({
                                    "title": chunk.web.title or "F1 Reference",
                                    "url": link_url,
                                    "uri": link_url,
                                })
                                is_grounded = True

                findings = [line.strip() for line in summary.split("\n") if line.strip().startswith(("-", "•", "*", "1.", "2."))]
                if not findings:
                    findings = [summary[:200] + "..."]

            except Exception as e:
                logger.exception(f"Gemini grounding search error: {e}")
                summary = f"Research inquiry processed with offline fallback: {query}"
                findings = [f"Web search unavailable: {str(e)}"]
                sources = [{"title": "Formula 1 Regulations & Historical Archive", "url": "https://www.formula1.com", "uri": "https://www.formula1.com"}]
                is_grounded = False

        exec_time = round((time.perf_counter() - t_start) * 1000, 2)

        # Store research payload in ArtifactStore
        dataset_metadata = {
            "domain": "research",
            "query": query,
            "sources_count": len(sources),
            "grounded": is_grounded,
        }
        dataset_id = self.artifact_store.put(
            data={
                "query": query,
                "summary": summary,
                "findings": findings,
                "sources": sources,
                "grounded": is_grounded,
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
            "execution_time_ms": exec_time,
            "trace": {
                "data_domain": "research",
                "query": query,
                "sources_count": len(sources),
                "grounding_provider": "gemini_google_search" if is_grounded else "offline_knowledge",
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
