"""
A2A (Agent-to-Agent) Registry and ASGI Router for PitWall AI.
Mounts AgentCard discovery endpoints (/.well-known/agent-card.json) and JSON-RPC / direct
execution routes for the 4 specialist agents:
- /a2a/historical
- /a2a/telemetry
- /a2a/research
- /a2a/viz
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Response
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel

from backend.app.a2a.agents.historical_agent import (
    HistoricalSQLAgent,
    get_historical_agent,
)
from backend.app.a2a.agents.telemetry_agent import (
    TelemetryAgent,
    get_telemetry_agent,
)
from backend.app.a2a.agents.research_agent import (
    ResearchAgent,
    get_research_agent,
)
from backend.app.a2a.agents.presentation_agent import (
    PresentationAgent,
    get_presentation_agent,
)

logger = logging.getLogger("pitwall.a2a.registry")

router = APIRouter(prefix="/a2a", tags=["A2A Agents"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class HistoricalQueryRequest(BaseModel):
    sql: Optional[str] = None
    question: Optional[str] = None
    chart_title: Optional[str] = None


class CornerCompareRequest(BaseModel):
    year: int
    grand_prix: str
    session_type: str = "Qualifying"
    driver_1: str
    driver_2: str
    corner: str
    lap_number_1: Optional[int] = None
    lap_number_2: Optional[int] = None


class FullLapCompareRequest(BaseModel):
    year: int
    grand_prix: str
    session_type: str = "Qualifying"
    driver_1: str
    driver_2: str
    lap_number_1: Optional[int] = None
    lap_number_2: Optional[int] = None


class TyreStintsRequest(BaseModel):
    year: int
    grand_prix: str
    session_type: str = "Race"
    drivers: Optional[List[str]] = None


class ResearchQueryRequest(BaseModel):
    query: str


class VizRenderRequest(BaseModel):
    dataset_id: str
    user_query: str = ""
    domain: Optional[str] = None
    summary: str = ""
    display_preferences: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Helper: Proto AgentCard to Dict
# ---------------------------------------------------------------------------

def _card_to_json(card) -> Dict[str, Any]:
    return MessageToDict(card, preserving_proto_field_name=True)


# ---------------------------------------------------------------------------
# 1. Historical Agent Endpoints (/a2a/historical)
# ---------------------------------------------------------------------------

@router.get("/historical/.well-known/agent-card.json")
async def historical_agent_card():
    """Agent Card for HistoricalSQLAgent."""
    card = HistoricalSQLAgent.get_agent_card()
    return _card_to_json(card)


@router.post("/historical/query")
async def historical_query(req: HistoricalQueryRequest):
    """Direct query endpoint for HistoricalSQLAgent (supports SQL or natural language questions)."""
    agent = get_historical_agent()
    if req.question:
        return agent.query(sql_or_query=req.question, chart_title=req.chart_title)
    if req.sql:
        return agent.execute_sql(sql=req.sql, chart_title=req.chart_title)
    raise HTTPException(status_code=400, detail="Must provide either 'sql' or 'question'")


@router.post("/historical")
async def historical_rpc(request: Request):
    """JSON-RPC / A2A generic execution endpoint for HistoricalSQLAgent."""
    body = await request.json()
    agent = get_historical_agent()

    params = body.get("params", {}) if isinstance(body.get("params"), dict) else {}
    sql = params.get("sql") or body.get("sql")
    question = params.get("question") or body.get("question")
    chart_title = params.get("chart_title") or body.get("chart_title")

    if question:
        result = agent.query(sql_or_query=question, chart_title=chart_title)
    elif sql:
        result = agent.execute_sql(sql=sql, chart_title=chart_title)
    else:
        raise HTTPException(status_code=400, detail="Missing 'sql' or 'question' in parameters")

    if "id" in body:
        return {"jsonrpc": "2.0", "result": result, "id": body["id"]}
    return result


# ---------------------------------------------------------------------------
# 2. Telemetry Agent Endpoints (/a2a/telemetry)
# ---------------------------------------------------------------------------

@router.get("/telemetry/.well-known/agent-card.json")
async def telemetry_agent_card():
    """Agent Card for TelemetryAgent."""
    card = TelemetryAgent.get_agent_card()
    return _card_to_json(card)


@router.post("/telemetry/compare-corners")
async def telemetry_compare_corners(req: CornerCompareRequest):
    """Direct corner comparison endpoint for TelemetryAgent."""
    agent = get_telemetry_agent()
    return agent.compare_corners(
        year=req.year,
        grand_prix=req.grand_prix,
        session_type=req.session_type,
        driver_1=req.driver_1,
        driver_2=req.driver_2,
        corner=req.corner,
        lap_number_1=req.lap_number_1,
        lap_number_2=req.lap_number_2,
    )


@router.post("/telemetry/compare-lap")
async def telemetry_compare_lap(req: FullLapCompareRequest):
    """Direct full-lap overlay endpoint for TelemetryAgent."""
    agent = get_telemetry_agent()
    return agent.compare_full_lap(
        year=req.year,
        grand_prix=req.grand_prix,
        session_type=req.session_type,
        driver_1=req.driver_1,
        driver_2=req.driver_2,
        lap_number_1=req.lap_number_1,
        lap_number_2=req.lap_number_2,
    )


@router.post("/telemetry/tyre-stints")
async def telemetry_tyre_stints(req: TyreStintsRequest):
    """Direct tyre degradation endpoint for TelemetryAgent."""
    agent = get_telemetry_agent()
    return agent.analyze_tyre_stints(
        year=req.year,
        grand_prix=req.grand_prix,
        session_type=req.session_type,
        drivers=req.drivers,
    )


@router.post("/telemetry")
async def telemetry_rpc(request: Request):
    """JSON-RPC / A2A generic execution endpoint for TelemetryAgent."""
    body = await request.json()
    params = body.get("params", body)
    agent = get_telemetry_agent()

    skill = body.get("method") or params.get("skill") or "compare_corners"
    if skill == "compare_full_lap":
        result = agent.compare_full_lap(
            year=params.get("year", 2024),
            grand_prix=params.get("grand_prix", "Monza"),
            session_type=params.get("session_type", "Qualifying"),
            driver_1=params.get("driver_1", "LEC"),
            driver_2=params.get("driver_2", "PIA"),
        )
    elif skill == "analyze_tyre_stints":
        result = agent.analyze_tyre_stints(
            year=params.get("year", 2024),
            grand_prix=params.get("grand_prix", "Monza"),
            session_type=params.get("session_type", "Race"),
            drivers=params.get("drivers", ["LEC"]),
        )
    else:
        result = agent.compare_corners(
            year=params.get("year", 2024),
            grand_prix=params.get("grand_prix", "Silverstone"),
            session_type=params.get("session_type", "Qualifying"),
            driver_1=params.get("driver_1", "VER"),
            driver_2=params.get("driver_2", "NOR"),
            corner=params.get("corner", "Copse"),
        )

    if "id" in body:
        return {"jsonrpc": "2.0", "result": result, "id": body["id"]}
    return result


# ---------------------------------------------------------------------------
# 3. Research Agent Endpoints (/a2a/research)
# ---------------------------------------------------------------------------

@router.get("/research/.well-known/agent-card.json")
async def research_agent_card():
    """Agent Card for ResearchAgent."""
    card = ResearchAgent.get_agent_card()
    return _card_to_json(card)


@router.post("/research/query")
async def research_query(req: ResearchQueryRequest):
    """Direct research query endpoint for ResearchAgent."""
    agent = get_research_agent()
    return agent.research_topic(req.query)


@router.post("/research")
async def research_rpc(request: Request):
    """JSON-RPC / A2A generic execution endpoint for ResearchAgent."""
    body = await request.json()
    params = body.get("params", body)
    agent = get_research_agent()

    query = params.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Missing 'query' parameter")

    result = agent.research_topic(query)
    if "id" in body:
        return {"jsonrpc": "2.0", "result": result, "id": body["id"]}
    return result


# ---------------------------------------------------------------------------
# 4. Presentation Agent Endpoints (/a2a/viz)
# ---------------------------------------------------------------------------

@router.get("/viz/.well-known/agent-card.json")
async def presentation_agent_card():
    """Agent Card for PresentationAgent."""
    card = PresentationAgent.get_agent_card()
    return _card_to_json(card)


@router.post("/viz/render")
async def presentation_render(req: VizRenderRequest):
    """Direct visualization render endpoint for PresentationAgent."""
    agent = get_presentation_agent()
    return agent.render_visualization(
        dataset_id=req.dataset_id,
        user_query=req.user_query,
        domain=req.domain,
        summary=req.summary,
        display_preferences=req.display_preferences,
    )


@router.post("/viz")
async def presentation_rpc(request: Request):
    """JSON-RPC / A2A generic execution endpoint for PresentationAgent."""
    body = await request.json()
    params = body.get("params", body)
    agent = get_presentation_agent()

    dataset_id = params.get("dataset_id")
    if not dataset_id:
        raise HTTPException(status_code=400, detail="Missing 'dataset_id' parameter")

    result = agent.render_visualization(
        dataset_id=dataset_id,
        user_query=params.get("user_query", ""),
        domain=params.get("domain"),
        summary=params.get("summary", ""),
        display_preferences=params.get("display_preferences"),
    )
    if "id" in body:
        return {"jsonrpc": "2.0", "result": result, "id": body["id"]}
    return result
