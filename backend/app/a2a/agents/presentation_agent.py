"""
Presentation & Visualization Specialist Agent for PitWall AI (A2A).
Consumes dataset_id from ArtifactStore and renders deterministic, WCAG AA compliant
dark HUD (#0B0F17) Plotly charts or Web Intelligence Cards conforming to the Pydantic VizSpec schema.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from google.adk.agents.llm_agent import LlmAgent
from a2a.types import AgentCard, AgentSkill, AgentInterface

from backend.app.a2a.artifact_store import get_artifact_store
from backend.app.charts.historical_charts import auto_build_historical_chart
from backend.app.charts.plotly_theme import HUD_BG_COLOR

logger = logging.getLogger("pitwall.a2a.presentation")


class VizSpec(BaseModel):
    """Pydantic model representing a rendered visualization specification."""
    viz_type: str = Field(default="plotly_figure", description="Type: 'plotly_figure', 'web_intelligence_card', or 'table'")
    chart_type: str = Field(default="plotly_figure", description="Legacy alias for viz_type")
    figure: Optional[Dict[str, Any]] = Field(default=None, description="Plotly JSON payload conforming to dark HUD standard")
    web_intelligence_card: Optional[Dict[str, Any]] = Field(default=None, description="Structured web research card")
    web_card: Optional[Dict[str, Any]] = Field(default=None, description="Legacy alias for web_intelligence_card")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Standardized telemetry/historical metadata")
    summary: str = Field(default="", description="Engineer takeaway or visual summary")


class PresentationAgent:
    """Specialist agent for turning data artifacts into dark HUD visuals."""

    def __init__(self, name: str = "presentation_agent"):
        self.name = name
        self.artifact_store = get_artifact_store()
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> LlmAgent:
        """Create ADK LlmAgent wrapper."""
        return LlmAgent(
            name=self.name,
            model="gemini-3.8-flash",
            instruction=(
                "You are the PitWall AI Presentation & Graphics Specialist. Transform dataset artifacts into "
                "dark HUD (#0B0F17) Plotly visualizations and intelligence cards. Ensure strict WCAG AA contrast."
            ),
            tools=[self.render_visualization],
        )

    def render_visualization(
        self,
        dataset_id: str,
        user_query: str = "",
        domain: Optional[str] = None,
        summary: str = "",
        display_preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve data from ArtifactStore[dataset_id] and produce a deterministic VizSpec.
        """
        record = self.artifact_store.get(dataset_id)
        if not record:
            logger.warning(f"Artifact not found for dataset_id='{dataset_id}'.")
            spec = VizSpec(
                viz_type="table",
                chart_type="table",
                figure=None,
                web_intelligence_card=None,
                web_card=None,
                metadata={"domain": domain or "unknown", "error": "Artifact expired or not found"},
                summary=f"No stored artifact found for id '{dataset_id}'.",
            )
            return spec.model_dump()

        data = record.get("data")
        artifact_meta = record.get("metadata", {})
        active_domain = domain or artifact_meta.get("domain", "historical_sql")

        # 1. Historical SQL Domain
        if active_domain == "historical_sql":
            sql = artifact_meta.get("sql", "")
            columns = artifact_meta.get("columns", [])
            data_rows = data if isinstance(data, list) else []

            chart_result = auto_build_historical_chart(
                sql=sql,
                columns=columns,
                data=data_rows,
                title_hint=artifact_meta.get("chart_title") or user_query,
            )

            fig_payload = None
            metadata = {
                "domain": "historical_sql",
                "sql": sql,
                "row_count": len(data_rows),
                "mode_label": "Historical Statistics",
            }

            if chart_result and "figure" in chart_result:
                fig_payload = chart_result["figure"]
                metadata = chart_result.get("metadata", metadata)

            if not fig_payload:
                fig_payload = {
                    "data": [],
                    "layout": {
                        "paper_bgcolor": HUD_BG_COLOR,
                        "plot_bgcolor": HUD_BG_COLOR,
                        "title": {"text": summary or "Historical Result Table"},
                    },
                }

            spec = VizSpec(
                viz_type="plotly_figure",
                chart_type="plotly_figure",
                figure=fig_payload,
                metadata=metadata,
                summary=summary or f"Historical data plotted with {len(data_rows)} rows.",
            )
            return spec.model_dump()

        # 2. Corner Telemetry Domain
        elif active_domain == "corner_telemetry":
            chart_spec = data.get("chart_spec") if isinstance(data, dict) else None
            meta = (
                data.get("metadata")
                if isinstance(data, dict) and data.get("metadata")
                else artifact_meta
            )
            if not chart_spec:
                chart_spec = {"data": [], "layout": {"paper_bgcolor": HUD_BG_COLOR, "plot_bgcolor": HUD_BG_COLOR}}

            spec = VizSpec(
                viz_type="plotly_figure",
                chart_type="plotly_figure",
                figure=chart_spec,
                metadata=meta,
                summary=summary or "Corner telemetry comparison rendered.",
            )
            return spec.model_dump()

        # 3. Full-Lap Telemetry Domain
        elif active_domain in ("full_lap_telemetry", "full_lap"):
            chart_spec = data.get("chart_spec") if isinstance(data, dict) else None
            meta = (
                data.get("metadata")
                if isinstance(data, dict) and data.get("metadata")
                else artifact_meta
            )
            if not chart_spec:
                chart_spec = {"data": [], "layout": {"paper_bgcolor": HUD_BG_COLOR, "plot_bgcolor": HUD_BG_COLOR}}

            spec = VizSpec(
                viz_type="plotly_figure",
                chart_type="plotly_figure",
                figure=chart_spec,
                metadata=meta,
                summary=summary or "Full lap telemetry overlay rendered.",
            )
            return spec.model_dump()

        # 4. Tyre Stint Degradation Domain
        elif active_domain in ("tyre_degradation", "tyre_stints"):
            chart_spec = data.get("chart_spec") if isinstance(data, dict) else None
            meta = (
                data.get("metadata")
                if isinstance(data, dict) and data.get("metadata")
                else artifact_meta
            )
            if not chart_spec:
                chart_spec = {"data": [], "layout": {"paper_bgcolor": HUD_BG_COLOR, "plot_bgcolor": HUD_BG_COLOR}}

            spec = VizSpec(
                viz_type="plotly_figure",
                chart_type="plotly_figure",
                figure=chart_spec,
                metadata=meta,
                summary=summary or "Tyre pace degradation scatter and regression rendered.",
            )
            return spec.model_dump()

        # 5. Research / Web Intelligence Domain
        elif active_domain == "research":
            raw_sources = data.get("sources", []) if isinstance(data, dict) else []
            formatted_sources = []
            for s in raw_sources:
                formatted_sources.append({
                    "title": s.get("title", "F1 Reference"),
                    "url": s.get("url") or s.get("uri", ""),
                })

            bullets = data.get("findings", []) if isinstance(data, dict) else []
            is_grounded = bool(data.get("grounded")) if isinstance(data, dict) else False

            card_payload = {
                "title": artifact_meta.get("query", user_query) or "Web Intelligence",
                "summary": data.get("summary", summary) if isinstance(data, dict) else summary,
                "bullets": bullets,
                "sources": formatted_sources,
                "grounded": is_grounded,
            }

            spec = VizSpec(
                viz_type="web_intelligence_card",
                chart_type="web_intelligence_card",
                figure=None,
                web_intelligence_card=card_payload,
                web_card=card_payload,
                metadata={
                    "domain": "research",
                    "mode_label": "Web Intelligence",
                    "sources_count": len(formatted_sources),
                    "grounded": is_grounded,
                },
                summary=summary or card_payload["summary"],
            )
            return spec.model_dump()

        # Default fallback
        spec = VizSpec(
            viz_type="table",
            chart_type="table",
            metadata={"domain": active_domain},
            summary=summary or "Raw data artifact presented.",
        )
        return spec.model_dump()

    @classmethod
    def get_agent_card(cls, base_url: str = "http://localhost:8000/a2a/viz") -> AgentCard:
        """Construct standard A2A AgentCard for PresentationAgent."""
        return AgentCard(
            name="presentation_agent",
            description="Formula 1 Dark HUD Data Visualization Agent rendering Plotly JSON figures and Web Intelligence cards.",
            version="1.0.0",
            supported_interfaces=[
                AgentInterface(url=base_url, protocol_binding="HTTP_JSON", protocol_version="1.0")
            ],
            skills=[
                AgentSkill(
                    id="render_visualization",
                    name="render_visualization",
                    description="Renders a stored dataset_id into a dark HUD Plotly chart or web intelligence card.",
                    tags=["visualization", "plotly", "charts", "hud"],
                )
            ],
        )


_presentation_agent_instance: Optional[PresentationAgent] = None


def get_presentation_agent() -> PresentationAgent:
    """Get singleton PresentationAgent."""
    global _presentation_agent_instance
    if _presentation_agent_instance is None:
        _presentation_agent_instance = PresentationAgent()
    return _presentation_agent_instance
