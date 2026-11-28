"""
Pytest suite for PitWall AI A2A Multi-Agent Architecture (Pass 1).
Validates:
1. All 4 /.well-known/agent-card.json endpoints return valid Agent Cards.
2. CircuitCornerEngine resolves Suzuka '130R' to Turn 15 (NOT Turn 130).
3. TelemetryAgent enforces 2023+ boundary and unknown corner handling.
4. HistoricalSQLAgent resolves Brazil 2021 (São Paulo GP) via alias self-correction + ArtifactStore.
5. PresentationAgent generates valid dark HUD Plotly figure payloads and web_intelligence_cards.
"""

import time
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.a2a.artifact_store import get_artifact_store
from backend.app.data.circuit_corners import get_circuit_corner_engine
from backend.app.a2a.agents.historical_agent import get_historical_agent
from backend.app.a2a.agents.telemetry_agent import get_telemetry_agent
from backend.app.a2a.agents.research_agent import get_research_agent
from backend.app.a2a.agents.presentation_agent import get_presentation_agent


@pytest.fixture(scope="module")
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Agent Card Endpoints
# ---------------------------------------------------------------------------

def test_agent_cards_endpoints(client):
    """Verify all 4 specialist agent card endpoints return valid A2A AgentCard specs."""
    endpoints = [
        ("/a2a/historical/.well-known/agent-card.json", "historical_agent"),
        ("/a2a/telemetry/.well-known/agent-card.json", "telemetry_agent"),
        ("/a2a/research/.well-known/agent-card.json", "research_agent"),
        ("/a2a/viz/.well-known/agent-card.json", "presentation_agent"),
    ]

    for path, expected_name in endpoints:
        res = client.get(path)
        assert res.status_code == 200, f"Failed GET {path}: {res.text}"
        data = res.json()
        assert data.get("name") == expected_name, f"Expected {expected_name}, got {data.get('name')}"
        assert data.get("version") == "1.0.0"
        assert len(data.get("skills", [])) >= 1, f"No skills listed for {expected_name}"
        assert len(data.get("supported_interfaces", [])) >= 1, f"No interfaces listed for {expected_name}"


# ---------------------------------------------------------------------------
# Test 2: CircuitCornerEngine Suzuka 130R Nickname Disambiguation
# ---------------------------------------------------------------------------

def test_circuit_corner_engine_disambiguation():
    """
    Verify nickname matching runs BEFORE turn number regex so '130R' NEVER resolves to Turn 130.
    """
    engine = get_circuit_corner_engine()

    # Suzuka 130R -> Turn 15
    res_130r = engine.resolve_corner("suzuka", "130R")
    assert res_130r["resolved"] is True
    assert res_130r["turn_number"] == 15, "130R MUST resolve to Turn 15, never Turn 130!"
    assert res_130r["coordinates"] is not None
    assert "x" in res_130r["coordinates"] and "y" in res_130r["coordinates"]

    # Silverstone Copse -> Turn 9
    res_copse = engine.resolve_corner("silverstone", "Copse")
    assert res_copse["resolved"] is True
    assert res_copse["turn_number"] == 9

    # Spa Eau Rouge -> Turn 2
    res_eau_rouge = engine.resolve_corner("spa", "Eau Rouge")
    assert res_eau_rouge["resolved"] is True
    assert res_eau_rouge["turn_number"] == 2

    # Monza Ascari -> Turn 8
    res_ascari = engine.resolve_corner("monza", "Ascari")
    assert res_ascari["resolved"] is True
    assert res_ascari["turn_number"] == 8

    # Interlagos Senna S -> Turn 1
    res_senna_s = engine.resolve_corner("interlagos", "Senna S")
    assert res_senna_s["resolved"] is True
    assert res_senna_s["turn_number"] == 1

    # Unknown corner
    res_unknown = engine.resolve_corner("suzuka", "unknown_corner_alias_xyz")
    assert res_unknown["resolved"] is False
    assert res_unknown.get("unknown_corner") is True
    assert "hint" in res_unknown


# ---------------------------------------------------------------------------
# Test 3: Telemetry Agent Era Boundary & Corner Hinting
# ---------------------------------------------------------------------------

def test_telemetry_agent_era_boundary_and_unknown_corner():
    """Verify TelemetryAgent blocks pre-2023 telemetry and handles unknown corners."""
    agent = get_telemetry_agent()

    # Pre-2023 boundary check
    res_2021 = agent.compare_corners(
        year=2021,
        grand_prix="Brazil",
        session_type="Qualifying",
        driver_1="HAM",
        driver_2="VER",
        corner="Senna S",
    )
    assert res_2021["success"] is False
    assert res_2021.get("era_boundary") is True
    assert "2023–present" in res_2021["message"]

    # Unknown corner handling
    res_unknown_corner = agent.compare_corners(
        year=2024,
        grand_prix="Suzuka",
        session_type="Qualifying",
        driver_1="VER",
        driver_2="NOR",
        corner="mysterious_unnamed_apex",
    )
    assert res_unknown_corner["success"] is False
    assert res_unknown_corner.get("unknown_corner") is True
    assert "hint" in res_unknown_corner


# ---------------------------------------------------------------------------
# Test 4: Historical SQL Agent Brazil 2021 Alias Resolution & ArtifactStore
# ---------------------------------------------------------------------------

def test_historical_agent_brazil_2021_alias_and_artifact():
    """
    Verify HistoricalSQLAgent resolves 'Brazil' query (stored as 'São Paulo Grand Prix' in 2021),
    executes successfully via zero-row self-correction, and stores results in ArtifactStore.
    """
    agent = get_historical_agent()
    store = get_artifact_store()

    # Query using colloquial 'Brazil' filter (stored as 'São Paulo Grand Prix' in 2021)
    sql = (
        "SELECT driver_code, constructor, position "
        "FROM v_race_results "
        "WHERE year = 2021 AND lower(grand_prix) LIKE '%brazil%' "
        "ORDER BY position LIMIT 3"
    )

    res = agent.execute_sql(sql, chart_title="2021 Brazil GP Podium")
    assert res["success"] is True
    assert res["row_count"] >= 3, f"Expected podium finishers, got {res['row_count']}"

    # Verify top 3: HAM, VER, BOT
    podium_drivers = [row["driver_code"] for row in res["sample_rows"][:3]]
    assert "HAM" in podium_drivers
    assert "VER" in podium_drivers

    # Verify dataset was stored in ArtifactStore
    dataset_id = res["dataset_id"]
    assert dataset_id is not None
    record = store.get(dataset_id)
    assert record is not None
    assert len(record["data"]) >= 3
    assert record["metadata"]["domain"] == "historical_sql"


def test_historical_agent_table_alias_and_unqualified_rewrites():
    """
    Assert both unqualified ('grand_prix LIKE %Brazil%') and table-aliased
    ('lower(w1.grand_prix) LIKE %brazil%') rewrite into valid executable DuckDB SQL.
    """
    agent = get_historical_agent()

    # 1. Unqualified
    sql_unqualified = (
        "SELECT driver_code, position FROM v_race_results "
        "WHERE year = 2021 AND grand_prix LIKE '%Brazil%' ORDER BY position LIMIT 3"
    )
    res_unq = agent.execute_sql(sql_unqualified)
    assert res_unq["success"] is True, f"Failed: {res_unq.get('error')}"
    assert res_unq["row_count"] >= 3
    assert any(r["driver_code"] == "HAM" for r in res_unq["sample_rows"])

    # 2. Table-aliased
    sql_aliased = (
        "SELECT w1.driver_code, w1.position FROM v_race_results w1 "
        "WHERE w1.year = 2021 AND lower(w1.grand_prix) LIKE '%brazil%' ORDER BY w1.position LIMIT 3"
    )
    res_aliased = agent.execute_sql(sql_aliased)
    assert res_aliased["success"] is True, f"Failed: {res_aliased.get('error')}"
    assert res_aliased["row_count"] >= 3
    assert any(r["driver_code"] == "HAM" for r in res_aliased["sample_rows"])


# ---------------------------------------------------------------------------
# Test 5: Presentation Agent VizSpec Generation
# ---------------------------------------------------------------------------

def test_presentation_agent_renders_viz_specs():
    """
    Verify PresentationAgent produces valid VizSpec payloads from ArtifactStore:
    - Plotly figure for historical SQL
    - Plotly figure for corner telemetry
    - Web intelligence card for research
    """
    pa = get_presentation_agent()
    store = get_artifact_store()

    # 1. Historical SQL Artifact
    hist_dataset_id = store.put(
        data=[
            {"driver_code": "HAM", "points": 25},
            {"driver_code": "VER", "points": 18},
            {"driver_code": "BOT", "points": 15},
        ],
        metadata={
            "domain": "historical_sql",
            "sql": "SELECT driver_code, points FROM v_race_results",
            "columns": ["driver_code", "points"],
            "chart_title": "Points Distribution",
        },
    )

    spec_hist = pa.render_visualization(
        dataset_id=hist_dataset_id,
        user_query="Who scored points?",
    )
    assert spec_hist["viz_type"] == "plotly_figure"
    assert spec_hist["chart_type"] in ("plotly_figure", "table")
    assert spec_hist["figure"] is not None
    assert spec_hist["metadata"]["domain"] == "historical_sql"

    # 2. Corner Telemetry Artifact
    dummy_corner_figure = {
        "data": [{"x": [0, 100, 200], "y": [250, 120, 280], "type": "scatter", "name": "VER"}],
        "layout": {"title": "Copse Corner Speed", "paper_bgcolor": "#0B0F17"},
    }
    telemetry_dataset_id = store.put(
        data={
            "chart_spec": dummy_corner_figure,
            "metadata": {
                "domain": "telemetry",
                "year": 2024,
                "grand_prix": "British Grand Prix",
                "session_name": "Qualifying",
                "mode_label": "Copse • Turn 9",
                "drivers": [{"code": "VER", "name": "Red Bull Racing", "color": "#3671C6"}],
            },
        },
        metadata={"domain": "corner_telemetry"},
    )

    spec_tel = pa.render_visualization(
        dataset_id=telemetry_dataset_id,
        domain="corner_telemetry",
    )
    assert spec_tel["viz_type"] == "plotly_figure"
    assert spec_tel["chart_type"] == "plotly_figure"
    assert spec_tel["figure"] is not None
    assert spec_tel["figure"]["layout"]["paper_bgcolor"] == "#0B0F17"

    # 3. Research Artifact -> web_intelligence_card
    research_dataset_id = store.put(
        data={
            "summary": "2026 F1 engine regulations introduce 50% electrical power split and 100% sustainable fuels.",
            "findings": ["MGU-H removed", "100% sustainable fuels", "350kW electric output"],
            "sources": [{"title": "FIA Technical Regulations", "uri": "https://fia.com"}],
            "grounded": True,
        },
        metadata={"domain": "research", "query": "2026 engine regulations"},
    )

    spec_research = pa.render_visualization(
        dataset_id=research_dataset_id,
        domain="research",
        user_query="2026 engine regulations",
    )
    assert spec_research["viz_type"] == "web_intelligence_card"
    assert spec_research["chart_type"] == "web_intelligence_card"
    assert spec_research["figure"] is None
    assert spec_research["web_intelligence_card"] is not None
    assert spec_research["web_card"] is not None
    assert len(spec_research["web_card"]["sources"]) >= 1
    assert "sustainable fuels" in spec_research["web_card"]["summary"]


# ---------------------------------------------------------------------------
# Test 6: Telemetry Agent Suzuka 130R Corner Telemetry via API & Viz
# ---------------------------------------------------------------------------

def test_telemetry_compare_corners_suzuka_130r(client, auth_header):
    """Verify POST /a2a/telemetry/compare-corners resolves 130R to Turn 15, stores artifact and renders viz."""
    res = client.post("/a2a/telemetry/compare-corners", headers=auth_header, json={
        "year": 2024,
        "grand_prix": "Suzuka",
        "session_type": "Qualifying",
        "driver_1": "VER",
        "driver_2": "NOR",
        "corner": "130R",
    })
    assert res.status_code == 200, f"Error: {res.text}"
    data = res.json()
    assert data["success"] is True, f"Failed: {data}"
    assert data["dataset_id"] is not None
    assert data["corner_info"]["turn_number"] == 15
    assert "metrics" in data
    assert "apex_min_speed_kph" in data["metrics"]
    assert "Apex speeds: VER: 300.0 km/h, NOR: 301.0 km/h" in data["summary"]
    assert "Apex speeds: {}" not in data["summary"]

    # Verify rendering via PresentationAgent
    r_viz = client.post("/a2a/viz/render", headers=auth_header, json={
        "dataset_id": data["dataset_id"],
        "domain": "corner_telemetry",
    })
    assert r_viz.status_code == 200
    viz_data = r_viz.json()
    assert viz_data["viz_type"] == "plotly_figure"
    assert viz_data["chart_type"] == "plotly_figure"
    assert viz_data["figure"] is not None
    driver_codes = [d["code"] if isinstance(d, dict) else d for d in viz_data["metadata"]["drivers"]]
    assert "VER" in driver_codes and "NOR" in driver_codes


# ---------------------------------------------------------------------------
# Test 7: Telemetry Agent Montreal Russell vs Verstappen 0.000s Delta
# ---------------------------------------------------------------------------

def test_telemetry_compare_full_lap_montreal(client, auth_header):
    """Verify POST /a2a/telemetry/compare-lap computes Montreal 1:12.000 vs 1:12.000 (0.000s delta) and renders."""
    res = client.post("/a2a/telemetry/compare-lap", headers=auth_header, json={
        "year": 2024,
        "grand_prix": "Canadian Grand Prix",
        "session_type": "Qualifying",
        "driver_1": "RUS",
        "driver_2": "VER",
        "lap_number_1": 22,
        "lap_number_2": 26,
    })
    assert res.status_code == 200, f"Error: {res.text}"
    data = res.json()
    assert data["success"] is True, f"Failed: {data}"
    assert data["dataset_id"] is not None
    lap_times = data["metrics"]["lap_times"]
    assert lap_times["driver_a"] == 72.0
    assert lap_times["driver_b"] == 72.0
    assert lap_times["delta_s"] == 0.0
    assert data["driver_1_lap_time"] == "1:12.000"
    assert data["driver_2_lap_time"] == "1:12.000"
    assert data["faster_driver"] == "TIE"

    # Verify rendering via PresentationAgent
    r_viz = client.post("/a2a/viz/render", headers=auth_header, json={
        "dataset_id": data["dataset_id"],
        "domain": "full_lap_telemetry",
    })
    assert r_viz.status_code == 200
    viz_data = r_viz.json()
    assert viz_data["viz_type"] == "plotly_figure"
    assert viz_data["chart_type"] == "plotly_figure"
    assert viz_data["figure"] is not None
    driver_codes = [d["code"] if isinstance(d, dict) else d for d in viz_data["metadata"]["drivers"]]
    assert "RUS" in driver_codes and "VER" in driver_codes


# ---------------------------------------------------------------------------
# Test 8: Telemetry Agent Tyre Stints Monza 2024 (Pair vs Solo LEC)
# ---------------------------------------------------------------------------

def test_telemetry_tyre_stints_pair_and_solo(client, auth_header):
    """Verify POST /a2a/telemetry/tyre-stints returns distinct dataset_ids and solo LEC renders only Leclerc."""
    # Pair: LEC vs PIA
    res_pair = client.post("/a2a/telemetry/tyre-stints", headers=auth_header, json={
        "year": 2024,
        "grand_prix": "Italian Grand Prix",
        "session_type": "Race",
        "drivers": ["LEC", "PIA"],
    })
    assert res_pair.status_code == 200, f"Pair failed: {res_pair.text}"
    data_pair = res_pair.json()
    assert data_pair["success"] is True
    assert data_pair["dataset_id"] is not None

    # Solo: LEC
    res_solo = client.post("/a2a/telemetry/tyre-stints", headers=auth_header, json={
        "year": 2024,
        "grand_prix": "Italian Grand Prix",
        "session_type": "Race",
        "drivers": ["LEC"],
    })
    assert res_solo.status_code == 200, f"Solo failed: {res_solo.text}"
    data_solo = res_solo.json()
    assert data_solo["success"] is True
    assert data_solo["dataset_id"] is not None
    assert data_pair["dataset_id"] != data_solo["dataset_id"], "Dataset IDs must be distinct"

    # Verify solo LEC renders with only Leclerc driver metadata
    r_viz_solo = client.post("/a2a/viz/render", headers=auth_header, json={
        "dataset_id": data_solo["dataset_id"],
        "domain": "tyre_degradation",
    })
    assert r_viz_solo.status_code == 200
    viz_solo = r_viz_solo.json()
    assert viz_solo["viz_type"] == "plotly_figure"
    assert viz_solo["chart_type"] == "plotly_figure"
    assert viz_solo["figure"] is not None
    solo_codes = [d["code"] if isinstance(d, dict) else d for d in viz_solo["metadata"]["drivers"]]
    assert solo_codes == ["LEC"], f"Expected only ['LEC'], got {solo_codes}"


# ---------------------------------------------------------------------------
# Test 9: Historical SQL Agent NL Question & 0-Row Guardrail
# ---------------------------------------------------------------------------

def test_historical_agent_nl_and_zero_row_guardrail(client, auth_header):
    """Verify HistoricalSQLAgent supports natural language questions and does not store 0-row artifacts."""
    # Natural Language question
    res_nl = client.post("/a2a/historical/query", headers=auth_header, json={
        "question": "Who won the 2021 Brazilian Grand Prix?",
    })
    assert res_nl.status_code == 200, f"NL query failed: {res_nl.text}"
    data_nl = res_nl.json()
    assert data_nl["success"] is True
    assert data_nl["row_count"] >= 1
    assert data_nl["dataset_id"] is not None
    assert any(
        row.get("driver_code") == "HAM" or "Hamilton" in str(row.get("driver_name", ""))
        for row in data_nl["sample_rows"]
    )

    # 0-Row Query: must return success: False and dataset_id: None (never stored)
    res_zero = client.post("/a2a/historical/query", headers=auth_header, json={
        "sql": "SELECT driver_code FROM v_race_results WHERE year = 1800",
    })
    assert res_zero.status_code == 200
    data_zero = res_zero.json()
    assert data_zero["success"] is False
    assert data_zero["row_count"] == 0
    assert data_zero["dataset_id"] is None


# ---------------------------------------------------------------------------
# Test 10: Research Agent Structured Sources and Offline Fallback
# ---------------------------------------------------------------------------

def test_research_agent_sources_and_offline_fallback(client, auth_header):
    """Verify ResearchAgent returns structured sources [{title, url}], dataset_id, and renders web_card."""
    agent = get_research_agent()
    result = agent.research_topic("What happened between Verstappen and Hamilton at Turn 4 during the 2021 Brazilian GP?")

    assert result["success"] is True
    assert result["dataset_id"] is not None
    assert len(result["sources"]) >= 1
    for src in result["sources"]:
        assert "title" in src
        assert "url" in src or "uri" in src
        if result.get("grounded"):
            assert (src.get("url") or src.get("uri", "")).startswith("http")
    assert "grounded" in result

    # Viz rendering
    r_viz = client.post("/a2a/viz/render", headers=auth_header, json={
        "dataset_id": result["dataset_id"],
        "domain": "research",
    })
    assert r_viz.status_code == 200
    viz_data = r_viz.json()
    assert viz_data["viz_type"] == "web_intelligence_card"
    assert viz_data["chart_type"] == "web_intelligence_card"
    assert viz_data["figure"] is None
    assert viz_data["web_intelligence_card"] is not None
    assert viz_data["web_card"] is not None
    assert len(viz_data["web_card"]["sources"]) >= 1
    assert "title" in viz_data["web_intelligence_card"]
    assert "summary" in viz_data["web_intelligence_card"]
    assert "bullets" in viz_data["web_intelligence_card"]


# ---------------------------------------------------------------------------
# Test 11: KPI Card, Data Table Fallback, ThinkingConfig & Faster-Driver Attribution
# ---------------------------------------------------------------------------

def test_presentation_kpi_card_and_data_table_fallback():
    """Verify 1-row SQL renders kpi_card and non-numeric multi-row renders data_table (never blank Plotly)."""
    pa = get_presentation_agent()
    store = get_artifact_store()

    # 1. Single-row scalar lookup -> kpi_card
    ds_one = store.put(
        data=[{
            "year": 2021,
            "grand_prix": "São Paulo Grand Prix",
            "driver_name": "Lewis Hamilton",
            "constructor": "Mercedes",
            "grid": 10,
            "position": 1,
            "winning_margin_s": 10.496,
        }],
        metadata={
            "domain": "historical_sql",
            "sql": "SELECT year, grand_prix, driver_name, constructor, grid, position FROM v_race_results LIMIT 1",
            "columns": ["year", "grand_prix", "driver_name", "constructor", "grid", "position", "winning_margin_s"],
            "chart_title": "Who won the 2021 Brazilian GP?",
        },
    )
    kpi_spec = pa.render_visualization(
        dataset_id=ds_one,
        user_query="Who won the 2021 Brazilian GP?",
        summary="Retrieved 1 rows across columns ['driver_name'] in 5ms. Dataset stored under dataset_id='abc'.",
    )
    assert kpi_spec["viz_type"] == "kpi_card"
    assert kpi_spec["figure"] is None
    assert "Dataset stored under" not in kpi_spec["title"]
    assert "Retrieved 1 rows" not in kpi_spec["summary"]
    assert kpi_spec["kpi_card"]["subtitle"] == "2021 São Paulo Grand Prix"
    labels = {m["label"]: m["value"] for m in kpi_spec["kpi_card"]["metrics"]}
    assert labels["Winner"] == "Lewis Hamilton"
    assert labels["Constructor"] == "Mercedes"
    assert labels["Grid"] == "P10"
    assert labels["Winning Margin"] == "+10.496s"

    # 2. Multi-row non-numeric classification table -> data_table (never empty Plotly canvas)
    ds_table = store.put(
        data=[
            {"position": 1, "driver_name": "Lewis Hamilton", "driver_code": "HAM", "constructor": "Mercedes", "grid": 10, "status": "Finished"},
            {"position": 2, "driver_name": "Max Verstappen", "driver_code": "VER", "constructor": "Red Bull", "grid": 2, "status": "Finished"},
        ],
        metadata={
            "domain": "historical_sql",
            "sql": "SELECT position, driver_name, driver_code, constructor, grid, status FROM v_race_results WHERE year = 2021 LIMIT 2",
            "columns": ["position", "driver_name", "driver_code", "constructor", "grid", "status"],
            "chart_title": "2021 Brazilian GP Classification",
        },
    )
    tbl_spec = pa.render_visualization(dataset_id=ds_table, user_query="2021 Brazilian GP Classification")
    assert tbl_spec["viz_type"] == "data_table"
    assert tbl_spec["figure"] is None
    assert tbl_spec["data_table"] is not None
    assert len(tbl_spec["data_table"]["rows"]) == 2


def test_full_lap_faster_driver_explicit_attribution():
    """Verify TelemetryAgent.compare_full_lap explicitly names the faster driver matching the lower lap time."""
    agent = get_telemetry_agent()
    res = agent.compare_full_lap(
        year=2024,
        grand_prix="Monza",
        session_type="Qualifying",
        driver_1="VER",
        driver_2="NOR",
    )
    assert res["success"] is True
    assert "driver_1_lap_time" in res
    assert "driver_2_lap_time" in res
    assert res["faster_driver"] == "NOR"
    assert "faster_driver=NOR" in res["summary"]
    assert "Stored in artifact" not in res["summary"]


def test_thinking_config_helper_selection():
    """Verify build_thinking_config disables budget on 2.5 models and minimizes thinking on flash-lite."""
    from backend.app.config import build_thinking_config

    cfg_25 = build_thinking_config("gemini-2.5-flash")
    assert cfg_25 is not None
    assert getattr(cfg_25, "thinking_budget", None) == 0

    cfg_lite = build_thinking_config("gemini-3.5-flash-lite")
    assert cfg_lite is not None
    lvl = str(getattr(cfg_lite, "thinking_level", "")).lower()
    assert "minimal" in lvl or "low" in lvl
