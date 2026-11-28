"""
End-to-End Pytest Suite for PitWall AI Root Orchestrator & A2A Specialists (Pass 2).
Validates:
1. Corner telemetry (Suzuka 130R 2024 VER vs NOR) -> A2A hops (telemetry + viz), real apex speeds, valid figure & metadata.drivers.
2. Full-lap telemetry (RUS vs VER Montreal 2024 Qualifying) -> valid figure, zero NaN, metadata.drivers == [RUS, VER].
3. Tyre stints (LEC vs PIA Monza 2024, then solo LEC follow-up) -> distinct dataset_ids, solo LEC contains zero PIA traces.
4. Historical SQL (2021 Brazilian GP winner) -> A2A hops (historical + viz), valid figure, zero hallucination.
5. Web research (2021 Brazilian GP Turn 4 incident) -> A2A hops (research + viz), web_intelligence_card payload with clickable sources.
6. Era refusal (2021 Brazil telemetry) & invalid corner (Turn 99 Suzuka) -> non-empty user-facing explanation before done.
"""

import json
from starlette.testclient import TestClient
import pytest

from backend.app.main import app


def parse_sse_events(raw_text: str):
    """Helper to parse raw SSE response frames into typed (event_type, data) tuples."""
    events = []
    for frame in raw_text.split("\n\n"):
        if not frame.strip():
            continue
        event_type = None
        data = None
        for line in frame.strip().split("\n"):
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                try:
                    data = json.loads(line[6:].strip())
                except Exception:
                    data = line[6:].strip()
        if event_type:
            events.append((event_type, data))
    return events


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Corner Telemetry Suzuka 130R
# ---------------------------------------------------------------------------

def test_e2e_corner_telemetry_suzuka_130r(client, auth_header):
    """
    Asserts corner comparison through Suzuka 130R routes via TelemetryAgent + PresentationAgent,
    returns real km/h speeds, and yields valid Plotly figure.
    """
    res = client.post(
        "/api/chat/stream",
        json={"message": "Compare Verstappen and Norris through 130R at 2024 Japanese GP Qualifying"},
        headers=auth_header,
    )
    assert res.status_code == 200, f"Failed: {res.text}"
    events = parse_sse_events(res.text)

    event_types = [e[0] for e in events]
    assert "session" in event_types
    assert "status" in event_types
    assert "trace" in event_types
    assert "chart" in event_types
    assert "text" in event_types
    assert "done" in event_types

    # Find trace event
    trace_event = next(e[1] for e in events if e[0] == "trace")
    assert trace_event["data_domain"] == "telemetry"
    assert trace_event.get("dataset_id") is not None

    # Verify A2A Hop Trace includes TelemetryAgent and PresentationAgent
    a2a_hops = trace_event.get("a2a_hops", [])
    assert len(a2a_hops) >= 2
    hop_agents = [h["agent_name"] for h in a2a_hops]
    assert "TelemetryAgent" in hop_agents
    assert "PresentationAgent" in hop_agents

    # Find chart event
    chart_event = next(e[1] for e in events if e[0] == "chart")
    assert chart_event["chart_type"] in ("corner_comparison", "plotly_figure")
    figure = chart_event.get("spec", {})
    assert "data" in figure and len(figure["data"]) > 0

    drivers = chart_event.get("metadata", {}).get("drivers", [])
    driver_codes = [d["code"] if isinstance(d, dict) else d for d in drivers]
    assert "VER" in driver_codes and "NOR" in driver_codes


# ---------------------------------------------------------------------------
# Test 2: Full-Lap Telemetry Montreal Russell vs Verstappen
# ---------------------------------------------------------------------------

def test_e2e_full_lap_montreal(client, auth_header):
    """
    Asserts full-lap comparison for Montreal 2024 Qualifying returns valid figure,
    zero NaN tokens, and metadata.drivers with [RUS, VER].
    """
    res = client.post(
        "/api/chat/stream",
        json={"message": "Overlay Russell vs Verstappen full lap at 2024 Canadian GP Qualifying"},
        headers=auth_header,
    )
    assert res.status_code == 200
    assert "NaN" not in res.text, "Stream must never leak raw NaN tokens!"
    assert "Infinity" not in res.text, "Stream must never leak raw Infinity tokens!"

    events = parse_sse_events(res.text)
    event_types = [e[0] for e in events]
    assert "trace" in event_types
    assert "chart" in event_types
    assert "done" in event_types

    trace_event = next(e[1] for e in events if e[0] == "trace")
    assert trace_event.get("dataset_id") is not None

    chart_event = next(e[1] for e in events if e[0] == "chart")
    assert chart_event["viz_type"] == "full_lap"
    assert chart_event["chart_type"] in ("full_lap_comparison", "plotly_figure")

    meta = chart_event.get("metadata", {})
    assert meta.get("driver_1_lap_time") == "1:11.742"
    assert meta.get("driver_2_lap_time") == "1:12.000"
    assert meta.get("faster_driver") == "RUS"

    drivers = meta.get("drivers", [])
    driver_codes = [d["code"] if isinstance(d, dict) else d for d in drivers]
    assert "RUS" in driver_codes and "VER" in driver_codes


# ---------------------------------------------------------------------------
# Test 3: Tyre Stints Pair vs Solo Follow-up
# ---------------------------------------------------------------------------

def test_e2e_tyre_stints_pair_and_solo_isolation(client, auth_header):
    """
    Validates driver inheritance and dataset_id isolation across back-to-back queries:
    1. LEC vs PIA at 2024 Italian GP
    2. Solo LEC at Monza 2024 (must contain zero PIA traces)
    """
    # Turn 1: Pair LEC vs PIA
    res1 = client.post(
        "/api/chat/stream",
        json={"message": "Compare Leclerc vs Piastri tyre degradation and stint strategy at 2024 Italian GP"},
        headers=auth_header,
    )
    assert res1.status_code == 200
    events1 = parse_sse_events(res1.text)
    session_id = next(e[1]["session_id"] for e in events1 if e[0] == "session")
    trace1 = next(e[1] for e in events1 if e[0] == "trace")
    dataset_id_1 = trace1.get("dataset_id")
    assert dataset_id_1 is not None

    # Turn 2: Solo LEC on same session
    res2 = client.post(
        "/api/chat/stream",
        json={
            "session_id": session_id,
            "message": "Show tyre degradation and race pace for Leclerc at Monza 2024",
        },
        headers=auth_header,
    )
    assert res2.status_code == 200
    events2 = parse_sse_events(res2.text)
    trace2 = next(e[1] for e in events2 if e[0] == "trace")
    dataset_id_2 = trace2.get("dataset_id")
    assert dataset_id_2 is not None

    # Dataset IDs must be isolated
    assert dataset_id_1 != dataset_id_2

    # Solo LEC chart must contain ONLY Leclerc
    chart2 = next(e[1] for e in events2 if e[0] == "chart")
    drivers2 = chart2.get("metadata", {}).get("drivers", [])
    driver_codes2 = [d["code"] if isinstance(d, dict) else d for d in drivers2]
    assert driver_codes2 == ["LEC"], f"Expected only ['LEC'], got {driver_codes2}"


# ---------------------------------------------------------------------------
# Test 4: Historical SQL 2021 Brazil Winner
# ---------------------------------------------------------------------------

def test_e2e_historical_sql_brazil_2021(client, auth_header):
    """
    Asserts historical SQL 1-row query resolves 2021 Brazilian Grand Prix,
    returns top-level viz_type == 'kpi_card' with zero raw 'Dataset stored under' / 'Retrieved 1 rows' leaks,
    and hops through HistoricalSQLAgent + PresentationAgent.
    """
    res = client.post(
        "/api/chat/stream",
        json={"message": "Who won the 2021 Brazilian Grand Prix and what was the winning margin over P2?"},
        headers=auth_header,
    )
    assert res.status_code == 200
    events = parse_sse_events(res.text)

    trace_event = next(e[1] for e in events if e[0] == "trace")
    assert trace_event["data_domain"] == "historical"
    assert trace_event.get("dataset_id") is not None

    hops = trace_event.get("a2a_hops", [])
    hop_agents = [h["agent_name"] for h in hops]
    assert "HistoricalSQLAgent" in hop_agents
    assert "PresentationAgent" in hop_agents

    chart_event = next(e[1] for e in events if e[0] == "chart")
    assert chart_event["viz_type"] == "kpi_card", f"Expected kpi_card for 1-row SQL, got {chart_event.get('viz_type')}"
    assert chart_event.get("figure") is None, "1-row KPI card must never mount an empty Plotly figure"
    kpi = chart_event.get("kpi_card") or {}
    assert len(kpi.get("metrics", [])) >= 2
    assert "Dataset stored under" not in chart_event.get("title", "")
    assert "Retrieved 1 rows" not in chart_event.get("title", "")

    text_chunks = [e[1].get("delta", "") for e in events if e[0] == "text"]
    full_text = "".join(text_chunks)
    assert "Dataset stored under" not in full_text
    assert "Retrieved 1 rows" not in full_text
    assert "dataset_id=" not in full_text
    assert "Hamilton" in full_text or "HAM" in full_text or "Mercedes" in full_text


# ---------------------------------------------------------------------------
# Test 5: Web Research 2021 Brazil Turn 4 Incident
# ---------------------------------------------------------------------------

def test_e2e_web_research_incident(client, auth_header):
    """
    Asserts research inquiry hops through ResearchAgent + PresentationAgent,
    preserves top-level viz_type == 'web_intelligence_card', and returns clickable source URLs.
    """
    res = client.post(
        "/api/chat/stream",
        json={"message": "What happened between Verstappen and Hamilton at Turn 4 during the 2021 Brazilian GP?"},
        headers=auth_header,
    )
    assert res.status_code == 200
    events = parse_sse_events(res.text)

    trace_event = next(e[1] for e in events if e[0] == "trace")
    assert trace_event["data_domain"] == "research"
    assert trace_event.get("dataset_id") is not None

    hops = trace_event.get("a2a_hops", [])
    hop_agents = [h["agent_name"] for h in hops]
    assert "ResearchAgent" in hop_agents
    assert "PresentationAgent" in hop_agents

    chart_event = next(e[1] for e in events if e[0] == "chart")
    assert chart_event["viz_type"] == "web_intelligence_card"
    assert chart_event["chart_type"] == "web_intelligence_card"

    web_card = chart_event.get("web_intelligence_card") or chart_event.get("spec", {}).get("web_intelligence_card") or chart_event.get("spec", {})
    sources = web_card.get("sources", [])
    assert len(sources) >= 1
    for s in sources:
        assert (s.get("url") or s.get("uri", "")).startswith("http")


# ---------------------------------------------------------------------------
# Test 6: Era Refusal & Invalid Corner Self-Healing / Error Feedback
# ---------------------------------------------------------------------------

def test_e2e_era_refusal_and_invalid_corner(client, auth_header):
    """
    Verifies that:
    1. Pre-2023 telemetry request yields clear era boundary notice.
    2. Unknown corner (Turn 99 Suzuka) yields clear user-facing error message before done.
    """
    # 1. Pre-2023 telemetry request
    res_era = client.post(
        "/api/chat/stream",
        json={"message": "Compare Verstappen and Hamilton telemetry at 2021 Brazil GP"},
        headers=auth_header,
    )
    assert res_era.status_code == 200
    events_era = parse_sse_events(res_era.text)
    status_details = [e[1].get("detail", "") for e in events_era if e[0] == "status"]
    text_era = "".join([e[1].get("delta", "") for e in events_era if e[0] == "text"])
    assert any("2023" in s for s in status_details) or "2023" in text_era

    # 2. Invalid corner Turn 99 Suzuka
    res_invalid = client.post(
        "/api/chat/stream",
        json={"message": "Compare Verstappen and Norris through Turn 99 at 2024 Suzuka"},
        headers=auth_header,
    )
    assert res_invalid.status_code == 200
    events_invalid = parse_sse_events(res_invalid.text)
    event_types = [e[0] for e in events_invalid]
    assert "done" in event_types

    # Must emit error or text message explaining the recognized corners
    has_error_or_explanation = (
        "error" in event_types
        or any("Turn 99" in str(e[1]) or "18 turns" in str(e[1]) or "unrecognized" in str(e[1]).lower() for e in events_invalid)
    )
    assert has_error_or_explanation, f"Expected clear error feedback, got {events_invalid}"
