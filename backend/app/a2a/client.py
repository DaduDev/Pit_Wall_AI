"""
Async A2A (Agent-to-Agent) Client for PitWall AI.
Discovers and communicates with the 4 mounted specialist agents:
- HistoricalSQLAgent (/a2a/historical)
- TelemetryAgent (/a2a/telemetry)
- ResearchAgent (/a2a/research)
- PresentationAgent (/a2a/viz)

Supports both ASGI in-process transport (default for single-process local dev & Cloud Run to prevent
self-call HTTP deadlocks) and standard HTTP transport via configurable base URL.
Records all A2A hops (agent, endpoint, latency, dataset_id, status) for live trace streaming.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
import logging
import os
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("pitwall.a2a.client")

# Propagates verified caller Authorization header cleanly across internal A2A hops
_ACTIVE_AUTH_HEADER: ContextVar[Optional[str]] = ContextVar("pitwall_active_auth_header", default=None)


def set_active_auth_header(auth_header: Optional[str]) -> Token:
    """Bind verified Bearer Authorization header for downstream A2A specialist calls."""
    return _ACTIVE_AUTH_HEADER.set(auth_header)


def reset_active_auth_header(token: Token) -> None:
    """Restore previous Authorization header context after request finishes."""
    _ACTIVE_AUTH_HEADER.reset(token)


def get_active_auth_header() -> Optional[str]:
    """Read active caller Authorization header if bound."""
    return _ACTIVE_AUTH_HEADER.get()


class A2AHopRecord:
    """Represents a single hop in an A2A agent invocation chain."""

    def __init__(
        self,
        agent_name: str,
        endpoint: str,
        duration_ms: float,
        dataset_id: Optional[str] = None,
        status: str = "success",
        error: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.endpoint = endpoint
        self.duration_ms = round(duration_ms, 2)
        self.dataset_id = dataset_id
        self.status = status
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "agent_name": self.agent_name,
            "endpoint": self.endpoint,
            "duration_ms": self.duration_ms,
            "status": self.status,
        }
        if self.dataset_id:
            d["dataset_id"] = self.dataset_id
        if self.error:
            d["error"] = self.error
        return d


class A2AClient:
    """
    Lightweight Async Client communicating with PitWall AI's specialist A2A agents.
    Tracks every hop for live engineering trace and telemetry auditing.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        app: Any = None,
        use_asgi: Optional[bool] = None,
    ):
        self.env_base_url = base_url or os.environ.get("A2A_BASE_URL")
        # Default to ASGI in-process transport if no external URL specified, preventing deadlocks
        if use_asgi is not None:
            self.use_asgi = use_asgi
        else:
            self.use_asgi = self.env_base_url is None

        self._app = app
        self._agent_cards: Dict[str, Dict[str, Any]] = {}
        self._hops: List[A2AHopRecord] = []
        self._client: Optional[httpx.AsyncClient] = None

    def _ensure_app(self) -> Any:
        if self._app is None:
            from backend.app.main import app as fastapi_app
            self._app = fastapi_app
        return self._app

    def _get_http_client(self) -> httpx.AsyncClient:
        """Returns or instantiates the httpx.AsyncClient with appropriate transport and auth forwarding."""
        async def _inject_auth_header(request: httpx.Request) -> None:
            auth_val = get_active_auth_header()
            if auth_val and "Authorization" not in request.headers:
                request.headers["Authorization"] = auth_val

        if self._client is None or self._client.is_closed:
            if self.use_asgi:
                app_instance = self._ensure_app()
                transport = httpx.ASGITransport(app=app_instance)
                self._client = httpx.AsyncClient(
                    transport=transport,
                    base_url="http://pitwall.internal",
                    timeout=180.0,
                    event_hooks={"request": [_inject_auth_header]},
                )
            else:
                base = self.env_base_url or "http://127.0.0.1:8000"
                self._client = httpx.AsyncClient(
                    base_url=base,
                    timeout=180.0,
                    event_hooks={"request": [_inject_auth_header]},
                )
        return self._client

    async def close(self):
        """Closes the underlying HTTP client session."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def clear_hops(self):
        """Resets the hop trace for a new turn or query."""
        self._hops.clear()

    def get_hops(self) -> List[Dict[str, Any]]:
        """Returns recorded A2A hops as dictionaries."""
        return [hop.to_dict() for hop in self._hops]

    def record_hop(
        self,
        agent_name: str,
        endpoint: str,
        duration_ms: float,
        dataset_id: Optional[str] = None,
        status: str = "success",
        error: Optional[str] = None,
    ):
        """Records a new hop in the active invocation chain."""
        self._hops.append(
            A2AHopRecord(
                agent_name=agent_name,
                endpoint=endpoint,
                duration_ms=duration_ms,
                dataset_id=dataset_id,
                status=status,
                error=error,
            )
        )

    # -----------------------------------------------------------------------
    # Agent Discovery
    # -----------------------------------------------------------------------

    async def discover_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        Discovers all 4 specialist agents via their /.well-known/agent-card.json endpoints.
        """
        client = self._get_http_client()
        discovery_targets = [
            ("historical_agent", "/a2a/historical/.well-known/agent-card.json"),
            ("telemetry_agent", "/a2a/telemetry/.well-known/agent-card.json"),
            ("research_agent", "/a2a/research/.well-known/agent-card.json"),
            ("presentation_agent", "/a2a/viz/.well-known/agent-card.json"),
        ]

        for agent_key, card_path in discovery_targets:
            try:
                res = await client.get(card_path)
                if res.status_code == 200:
                    self._agent_cards[agent_key] = res.json()
            except Exception as e:
                logger.warning(f"Could not discover AgentCard at {card_path}: {e}")

        return self._agent_cards

    # -----------------------------------------------------------------------
    # 1. Historical SQL Agent
    # -----------------------------------------------------------------------

    async def query_historical(
        self,
        question: Optional[str] = None,
        sql: Optional[str] = None,
        chart_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Delegates historical query to HistoricalSQLAgent (/a2a/historical/query).
        Supports natural language questions or raw SQL.
        """
        client = self._get_http_client()
        endpoint = "/a2a/historical/query"
        payload: Dict[str, Any] = {}
        if question:
            payload["question"] = question
        if sql:
            payload["sql"] = sql
        if chart_title:
            payload["chart_title"] = chart_title

        t0 = time.perf_counter()
        try:
            res = await client.post(endpoint, json=payload)
            dur = (time.perf_counter() - t0) * 1000
            if res.status_code == 200:
                data = res.json()
                self.record_hop(
                    agent_name="HistoricalSQLAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    dataset_id=data.get("dataset_id"),
                    status="success" if data.get("success", True) else "error",
                    error=data.get("error"),
                )
                return data
            else:
                err_msg = f"HTTP {res.status_code}: {res.text}"
                self.record_hop(
                    agent_name="HistoricalSQLAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    status="error",
                    error=err_msg,
                )
                return {"success": False, "error": err_msg}
        except Exception as e:
            dur = (time.perf_counter() - t0) * 1000
            self.record_hop(
                agent_name="HistoricalSQLAgent",
                endpoint=endpoint,
                duration_ms=dur,
                status="error",
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    # -----------------------------------------------------------------------
    # 2. Telemetry Agent
    # -----------------------------------------------------------------------

    async def compare_corners(
        self,
        year: int,
        grand_prix: str,
        driver_1: str,
        driver_2: str,
        corner: str,
        session_type: str = "Qualifying",
        lap_number_1: Optional[int] = None,
        lap_number_2: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Delegates corner telemetry comparison to TelemetryAgent (/a2a/telemetry/compare-corners).
        """
        client = self._get_http_client()
        endpoint = "/a2a/telemetry/compare-corners"
        payload = {
            "year": year,
            "grand_prix": grand_prix,
            "session_type": session_type,
            "driver_1": driver_1,
            "driver_2": driver_2,
            "corner": corner,
            "lap_number_1": lap_number_1,
            "lap_number_2": lap_number_2,
        }

        t0 = time.perf_counter()
        try:
            res = await client.post(endpoint, json=payload)
            dur = (time.perf_counter() - t0) * 1000
            if res.status_code == 200:
                data = res.json()
                self.record_hop(
                    agent_name="TelemetryAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    dataset_id=data.get("dataset_id"),
                    status="success" if data.get("success", True) else "error",
                    error=data.get("error"),
                )
                return data
            else:
                err_msg = f"HTTP {res.status_code}: {res.text}"
                self.record_hop(
                    agent_name="TelemetryAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    status="error",
                    error=err_msg,
                )
                return {"success": False, "error": err_msg}
        except Exception as e:
            dur = (time.perf_counter() - t0) * 1000
            self.record_hop(
                agent_name="TelemetryAgent",
                endpoint=endpoint,
                duration_ms=dur,
                status="error",
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    async def compare_lap(
        self,
        year: int,
        grand_prix: str,
        driver_1: str,
        driver_2: str,
        session_type: str = "Qualifying",
        lap_number_1: Optional[int] = None,
        lap_number_2: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Delegates full-lap telemetry overlay to TelemetryAgent (/a2a/telemetry/compare-lap).
        """
        client = self._get_http_client()
        endpoint = "/a2a/telemetry/compare-lap"
        payload = {
            "year": year,
            "grand_prix": grand_prix,
            "session_type": session_type,
            "driver_1": driver_1,
            "driver_2": driver_2,
            "lap_number_1": lap_number_1,
            "lap_number_2": lap_number_2,
        }

        t0 = time.perf_counter()
        try:
            res = await client.post(endpoint, json=payload)
            dur = (time.perf_counter() - t0) * 1000
            if res.status_code == 200:
                data = res.json()
                self.record_hop(
                    agent_name="TelemetryAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    dataset_id=data.get("dataset_id"),
                    status="success" if data.get("success", True) else "error",
                    error=data.get("error"),
                )
                return data
            else:
                err_msg = f"HTTP {res.status_code}: {res.text}"
                self.record_hop(
                    agent_name="TelemetryAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    status="error",
                    error=err_msg,
                )
                return {"success": False, "error": err_msg}
        except Exception as e:
            dur = (time.perf_counter() - t0) * 1000
            self.record_hop(
                agent_name="TelemetryAgent",
                endpoint=endpoint,
                duration_ms=dur,
                status="error",
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    async def analyze_tyre_stints(
        self,
        year: int,
        grand_prix: str,
        drivers: Optional[List[str]] = None,
        session_type: str = "Race",
    ) -> Dict[str, Any]:
        """
        Delegates tyre degradation & stint strategy to TelemetryAgent (/a2a/telemetry/tyre-stints).
        """
        client = self._get_http_client()
        endpoint = "/a2a/telemetry/tyre-stints"
        payload = {
            "year": year,
            "grand_prix": grand_prix,
            "session_type": session_type,
            "drivers": drivers or [],
        }

        t0 = time.perf_counter()
        try:
            res = await client.post(endpoint, json=payload)
            dur = (time.perf_counter() - t0) * 1000
            if res.status_code == 200:
                data = res.json()
                self.record_hop(
                    agent_name="TelemetryAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    dataset_id=data.get("dataset_id"),
                    status="success" if data.get("success", True) else "error",
                    error=data.get("error"),
                )
                return data
            else:
                err_msg = f"HTTP {res.status_code}: {res.text}"
                self.record_hop(
                    agent_name="TelemetryAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    status="error",
                    error=err_msg,
                )
                return {"success": False, "error": err_msg}
        except Exception as e:
            dur = (time.perf_counter() - t0) * 1000
            self.record_hop(
                agent_name="TelemetryAgent",
                endpoint=endpoint,
                duration_ms=dur,
                status="error",
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    # -----------------------------------------------------------------------
    # 3. Research Agent
    # -----------------------------------------------------------------------

    async def query_research(self, query: str) -> Dict[str, Any]:
        """
        Delegates web inquiry to ResearchAgent (/a2a/research/query) with Google Search grounding.
        """
        client = self._get_http_client()
        endpoint = "/a2a/research/query"
        payload = {"query": query}

        t0 = time.perf_counter()
        try:
            res = await client.post(endpoint, json=payload)
            dur = (time.perf_counter() - t0) * 1000
            if res.status_code == 200:
                data = res.json()
                self.record_hop(
                    agent_name="ResearchAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    dataset_id=data.get("dataset_id"),
                    status="success" if data.get("success", True) else "error",
                    error=data.get("error"),
                )
                return data
            else:
                err_msg = f"HTTP {res.status_code}: {res.text}"
                self.record_hop(
                    agent_name="ResearchAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    status="error",
                    error=err_msg,
                )
                return {"success": False, "error": err_msg}
        except Exception as e:
            dur = (time.perf_counter() - t0) * 1000
            self.record_hop(
                agent_name="ResearchAgent",
                endpoint=endpoint,
                duration_ms=dur,
                status="error",
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    async def resolve_and_learn_corner(self, circuit: str, corner_query: str) -> Dict[str, Any]:
        """
        Self-healing corner resolution: queries ResearchAgent (/a2a/research/resolve-corner)
        to cross-reference MultiViewer geometry and store learned aliases.
        """
        client = self._get_http_client()
        endpoint = "/a2a/research/resolve-corner"
        payload = {"circuit": circuit, "corner_query": corner_query}

        t0 = time.perf_counter()
        try:
            res = await client.post(endpoint, json=payload)
            dur = (time.perf_counter() - t0) * 1000
            if res.status_code == 200:
                data = res.json()
                self.record_hop(
                    agent_name="ResearchAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    status="success" if data.get("resolved", True) else "error",
                )
                return data
            else:
                err_msg = f"HTTP {res.status_code}: {res.text}"
                self.record_hop(
                    agent_name="ResearchAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    status="error",
                    error=err_msg,
                )
                return {"resolved": False, "error": err_msg}
        except Exception as e:
            dur = (time.perf_counter() - t0) * 1000
            self.record_hop(
                agent_name="ResearchAgent",
                endpoint=endpoint,
                duration_ms=dur,
                status="error",
                error=str(e),
            )
            return {"resolved": False, "error": str(e)}

    # -----------------------------------------------------------------------
    # 4. Presentation Agent
    # -----------------------------------------------------------------------

    async def render_viz(
        self,
        dataset_id: str,
        user_query: str = "",
        domain: Optional[str] = None,
        summary: str = "",
        display_preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delegates visual artifact rendering to PresentationAgent (/a2a/viz/render).
        Produces standardized Plotly figures or Web Intelligence cards.
        """
        client = self._get_http_client()
        endpoint = "/a2a/viz/render"
        payload = {
            "dataset_id": dataset_id,
            "user_query": user_query,
            "domain": domain,
            "summary": summary,
            "display_preferences": display_preferences,
        }

        t0 = time.perf_counter()
        try:
            res = await client.post(endpoint, json=payload)
            dur = (time.perf_counter() - t0) * 1000
            if res.status_code == 200:
                data = res.json()
                self.record_hop(
                    agent_name="PresentationAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    dataset_id=dataset_id,
                    status="success",
                )
                return data
            else:
                err_msg = f"HTTP {res.status_code}: {res.text}"
                self.record_hop(
                    agent_name="PresentationAgent",
                    endpoint=endpoint,
                    duration_ms=dur,
                    dataset_id=dataset_id,
                    status="error",
                    error=err_msg,
                )
                return {"chart_type": "table", "error": err_msg}
        except Exception as e:
            dur = (time.perf_counter() - t0) * 1000
            self.record_hop(
                agent_name="PresentationAgent",
                endpoint=endpoint,
                duration_ms=dur,
                dataset_id=dataset_id,
                status="error",
                error=str(e),
            )
            return {"chart_type": "table", "error": str(e)}


_global_a2a_client: Optional[A2AClient] = None


def get_a2a_client() -> A2AClient:
    """Singleton getter for A2AClient."""
    global _global_a2a_client
    if _global_a2a_client is None:
        _global_a2a_client = A2AClient()
    return _global_a2a_client
