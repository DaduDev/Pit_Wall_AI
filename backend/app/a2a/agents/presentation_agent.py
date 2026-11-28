"""
Presentation & Visualization Specialist Agent for PitWall AI (A2A).
Consumes dataset_id from ArtifactStore and renders deterministic, WCAG AA compliant
dark HUD (#0B0F17) Plotly charts or Web Intelligence Cards conforming to the Pydantic VizSpec schema.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from google.adk.agents.llm_agent import LlmAgent
from a2a.types import AgentCard, AgentSkill, AgentInterface

from backend.app.config import settings
from backend.app.a2a.artifact_store import get_artifact_store
from backend.app.charts.historical_charts import auto_build_historical_chart
from backend.app.charts.plotly_theme import HUD_BG_COLOR

logger = logging.getLogger("pitwall.a2a.presentation")

_INTERNAL_ID_COLS = {"race_id", "driver_id", "constructor_id", "circuit_id", "status_id", "finish_ms", "round"}


def _is_internal_tool_summary(text: str) -> bool:
    """Detect raw internal specialist diagnostic strings that must never leak to UI titles or chat."""
    if not text:
        return False
    low = text.lower()
    return (
        ("retrieved " in low and " across columns" in low)
        or "dataset_id=" in low
        or "stored in artifact" in low
        or "stored under dataset_id" in low
    )


def _derive_clean_title(
    user_query: str,
    artifact_meta: Dict[str, Any],
    data_rows: List[Dict[str, Any]],
) -> str:
    """Derive a clean, human-readable chart/card title without raw tool strings."""
    raw_hint = str(artifact_meta.get("chart_title") or "").strip()
    if raw_hint and not _is_internal_tool_summary(raw_hint):
        # If raw_hint is not a conversational question, keep it concise
        q_clean = raw_hint.rstrip("?").strip()
        if not q_clean.lower().startswith(("who ", "what ", "show ", "tell ", "give ", "list ", "how ")):
            return q_clean[:90]

    if data_rows:
        first = data_rows[0]
        yr = first.get("year")
        gp = first.get("grand_prix")
        if yr and gp:
            if len(data_rows) == 1 and first.get("position") == 1:
                return f"{yr} {gp} — Race Winner"
            if len(data_rows) == 1:
                return f"{yr} {gp} — Result Summary"
            return f"{yr} {gp} — Historical Classification"

    fallback_q = (user_query or raw_hint or "Formula 1 Historical Results").rstrip("?").strip()
    if _is_internal_tool_summary(fallback_q) or not fallback_q:
        return "Formula 1 Historical Results"
    return fallback_q[:90]


def _format_kpi_card(
    data_rows: List[Dict[str, Any]],
    columns: List[str],
    artifact_meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Build structured single-row KPI card payload {subtitle, metrics: [{label, value}]}."""
    row = data_rows[0] if data_rows else {}
    yr = row.get("year")
    gp = row.get("grand_prix")
    subtitle_parts = [str(p).strip() for p in (yr, gp) if p is not None and str(p).strip()]
    subtitle = " ".join(subtitle_parts) if subtitle_parts else "Official DuckDB Historical Result"

    metrics: List[Dict[str, str]] = []
    seen_keys: set[str] = set()

    has_full_driver = bool(row.get("driver_name"))

    def _add_metric(label: str, value: str, key: str) -> None:
        seen_keys.add(key)
        metrics.append({"label": label, "value": value})

    if row.get("driver_name"):
        lbl = "Winner" if row.get("position") == 1 else "Driver"
        _add_metric(lbl, str(row["driver_name"]), "driver_name")
        seen_keys.add("driver_code")
        seen_keys.add("surname")
        seen_keys.add("forename")
    elif row.get("driver_code"):
        lbl = "Winner" if row.get("position") == 1 else "Driver"
        _add_metric(lbl, str(row["driver_code"]), "driver_code")

    if row.get("constructor"):
        _add_metric("Constructor", str(row["constructor"]), "constructor")

    if row.get("grid") is not None:
        g_val = row["grid"]
        _add_metric("Grid", f"P{g_val}" if str(g_val).isdigit() else str(g_val), "grid")

    if row.get("position") is not None:
        pos_val = row["position"]
        if pos_val != 1 or not any(m["label"] == "Winner" for m in metrics):
            _add_metric("Finish Position", f"P{pos_val}" if str(pos_val).isdigit() else str(pos_val), "position")
        else:
            seen_keys.add("position")

    for margin_key in ("winning_margin_s", "margin_s", "gap_s", "winning_margin"):
        if row.get(margin_key) is not None:
            m_val = row[margin_key]
            try:
                _add_metric("Winning Margin", f"+{float(m_val):.3f}s", margin_key)
            except (TypeError, ValueError):
                _add_metric("Winning Margin", str(m_val), margin_key)
            break

    if row.get("finish_time"):
        _add_metric("Race Time", str(row["finish_time"]), "finish_time")

    if row.get("points") is not None:
        _add_metric("Points", str(row["points"]), "points")

    if row.get("laps") is not None:
        _add_metric("Laps", str(row["laps"]), "laps")

    for q_col in ("q3", "q2", "q1"):
        if row.get(q_col):
            _add_metric(q_col.upper(), str(row[q_col]), q_col)

    # Append any remaining non-internal columns cleanly
    skip_cols = seen_keys | _INTERNAL_ID_COLS | {"year", "grand_prix"}
    for col in columns or list(row.keys()):
        if col in skip_cols:
            continue
        if has_full_driver and col in ("driver_code", "forename", "surname"):
            continue
        val = row.get(col)
        if val is None or str(val).strip() == "":
            continue
        _add_metric(col.replace("_", " ").title(), str(val), col)

    return {
        "subtitle": subtitle,
        "metrics": metrics,
    }


def _format_data_table(
    data_rows: List[Dict[str, Any]],
    columns: List[str],
    artifact_meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Build structured dark HUD data table payload."""
    cols = [c for c in (columns or (list(data_rows[0].keys()) if data_rows else [])) if c not in _INTERNAL_ID_COLS]
    if not cols and data_rows:
        cols = list(data_rows[0].keys())

    first = data_rows[0] if data_rows else {}
    subtitle_parts = [str(p).strip() for p in (first.get("year"), first.get("grand_prix")) if p is not None and str(p).strip()]
    subtitle = " ".join(subtitle_parts) if subtitle_parts else f"{len(data_rows)} Verified Records"

    clean_rows = [{c: row.get(c) for c in cols} for row in data_rows[:50]]
    return {
        "subtitle": subtitle,
        "columns": cols,
        "rows": clean_rows,
    }


class VizSpec(BaseModel):
    """Pydantic model representing a rendered visualization specification."""
    viz_type: str = Field(default="plotly_figure", description="Type: 'plotly_figure', 'kpi_card', 'data_table', 'web_intelligence_card', or 'table'")
    chart_type: str = Field(default="plotly_figure", description="Legacy alias for viz_type")
    title: str = Field(default="", description="Clean human-readable title")
    figure: Optional[Dict[str, Any]] = Field(default=None, description="Plotly JSON payload conforming to dark HUD standard")
    minimap: Optional[Dict[str, Any]] = Field(default=None, description="Optional GPS track minimap Plotly payload")
    kpi_card: Optional[Dict[str, Any]] = Field(default=None, description="Single-row KPI card {subtitle, metrics}")
    data_table: Optional[Dict[str, Any]] = Field(default=None, description="Structured dark HUD table {subtitle, columns, rows}")
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
            model=settings.GEMINI_MODEL,
            instruction=(
                "You are the PitWall AI Presentation & Graphics Specialist. Transform dataset artifacts into "
                "dark HUD (#0B0F17) Plotly visualizations, KPI cards, Data Tables, and intelligence cards. Ensure strict WCAG AA contrast."
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
        safe_summary = "" if _is_internal_tool_summary(summary) else summary
        record = self.artifact_store.get(dataset_id)
        if not record:
            logger.warning(f"Artifact not found for dataset_id='{dataset_id}'.")
            spec = VizSpec(
                viz_type="data_table",
                chart_type="data_table",
                title="Data Unavailable",
                figure=None,
                data_table={"subtitle": "Artifact expired or not found", "columns": [], "rows": []},
                web_intelligence_card=None,
                web_card=None,
                metadata={"domain": domain or "unknown", "error": "Artifact expired or not found"},
                summary="No stored data available to render.",
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
            clean_title = _derive_clean_title(user_query, artifact_meta, data_rows)

            # 1-row scalar result -> KPI Card (never empty Plotly canvas)
            if len(data_rows) == 1:
                kpi_payload = _format_kpi_card(data_rows, columns, artifact_meta)
                row0 = data_rows[0]
                meta = {
                    "domain": "historical",
                    "year": row0.get("year"),
                    "grand_prix": row0.get("grand_prix"),
                    "session_name": "Official Race Result",
                    "mode_label": "Historical KPI Card • DuckDB",
                    "sql": sql,
                    "row_count": 1,
                    "drivers": [],
                }
                kpi_summary = safe_summary or (
                    f"{kpi_payload['subtitle']}: " + ", ".join(f"{m['label']} {m['value']}" for m in kpi_payload["metrics"][:4])
                )
                spec = VizSpec(
                    viz_type="kpi_card",
                    chart_type="kpi_card",
                    title=clean_title,
                    figure=None,
                    kpi_card=kpi_payload,
                    metadata=meta,
                    summary=kpi_summary,
                )
                return spec.model_dump()

            # Multi-row historical results -> Chart when sensible bar/line chart builds, else dark HUD Data Table
            chart_result = auto_build_historical_chart(
                sql=sql,
                columns=columns,
                data=data_rows,
                title_hint=clean_title,
            )

            fig_payload = None
            chart_kind = ""
            metadata = {
                "domain": "historical",
                "sql": sql,
                "row_count": len(data_rows),
                "mode_label": "Historical Analytics • DuckDB",
                "drivers": [],
            }

            if chart_result:
                fig_payload = chart_result.get("figure") or chart_result.get("spec")
                chart_kind = str(chart_result.get("chart_type") or "")
                raw_meta = chart_result.get("metadata")
                if isinstance(raw_meta, dict):
                    metadata = {**raw_meta, "domain": "historical_sql"}

            has_plot_traces = (
                isinstance(fig_payload, dict)
                and isinstance(fig_payload.get("data"), list)
                and len(fig_payload["data"]) > 0
            )

            # Never emit empty Plotly figure or Plotly table trace when structured dark HUD Data Table applies
            if len(data_rows) >= 2 and has_plot_traces and chart_kind != "table":
                spec = VizSpec(
                    viz_type="plotly_figure",
                    chart_type="plotly_figure",
                    title=clean_title,
                    figure=fig_payload,
                    metadata=metadata,
                    summary=safe_summary or f"{clean_title} ({len(data_rows)} verified records).",
                )
                return spec.model_dump()

            # Fallback for >=2 rows with no numeric chart (or 0 rows): clean dark HUD Data Table
            table_payload = _format_data_table(data_rows, columns, artifact_meta)
            spec = VizSpec(
                viz_type="data_table",
                chart_type="data_table",
                title=clean_title,
                figure=None,
                data_table=table_payload,
                metadata=metadata,
                summary=safe_summary or f"{clean_title} ({len(data_rows)} records).",
            )
            return spec.model_dump()

        # 2. Corner Telemetry Domain
        elif active_domain == "corner_telemetry":
            chart_spec = data.get("chart_spec") if isinstance(data, dict) else None
            minimap_spec = data.get("minimap_spec") if isinstance(data, dict) else None
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
                minimap=minimap_spec,
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

            from backend.app.a2a.agents.research_agent import sanitize_bullets, sanitize_summary_text
            from backend.app.llm import PROVIDER_LABELS

            raw_bullets = data.get("findings", []) if isinstance(data, dict) else []
            bullets = sanitize_bullets(raw_bullets)
            raw_summary = data.get("summary", summary) if isinstance(data, dict) else summary
            clean_card_summary = sanitize_summary_text(raw_summary)
            is_grounded = bool(data.get("grounded")) if isinstance(data, dict) else False
            provider = (
                data.get("provider")
                if isinstance(data, dict) and data.get("provider")
                else ("gemini" if is_grounded else "ollama_fallback")
            )
            provider_label = PROVIDER_LABELS.get(provider, PROVIDER_LABELS["ollama_fallback"])

            card_payload = {
                "title": artifact_meta.get("query", user_query) or "Web Intelligence",
                "summary": clean_card_summary,
                "bullets": bullets,
                "sources": formatted_sources,
                "grounded": is_grounded,
                "provider": provider,
                "provider_label": provider_label,
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
                    "provider": provider,
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
