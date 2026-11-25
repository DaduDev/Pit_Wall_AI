"""
Unit and Integration Tests for Tyre Stint Degradation & Race Strategy (Phase 6 / User Story 4).
Validates:
- Clean-lap outlier filtering logic:
  * Lap 1 (standing start) exclusion
  * is_pit_out_lap=True exclusion
  * Pit-in laps (from pit endpoint and stint transition) exclusion
  * Incomplete/null lap times exclusion
  * SC / VSC / traffic outliers (>107% of stint median clean lap time) exclusion
- Linear regression degradation slope calculation (sec/lap)
- Real cached OpenF1 2024 Italian GP Race integration (LEC 1-stop vs PIA 2-stop)
- 2-subplot synchronized dark HUD Plotly layout (#0B0F17) with Pirelli compound colors
- Engineering trace metadata verification
- Strict pre-2023 era boundary enforcement
- Missing / unknown driver error handling
"""

import asyncio
import pytest
import numpy as np
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.agent.tools.strategy import (
    analyze_tyre_stints,
    filter_clean_laps_and_compute_deg,
)
from backend.app.chat.streaming import format_trace_event
from backend.app.agent.orchestrator import RaceEngineerOrchestrator
from backend.app.chat.session import ConversationSession


def test_filter_clean_laps_outliers_and_slope():
    """
    Unit test for clean lap filtering and linear degradation slope calculation.
    """
    # 2-stint race setup
    stints = [
        {"stint_number": 1, "lap_start": 1, "lap_end": 10, "compound": "MEDIUM", "tyre_age_at_start": 0},
        {"stint_number": 2, "lap_start": 11, "lap_end": 20, "compound": "HARD", "tyre_age_at_start": 0},
    ]
    pit_stops = [{"lap_number": 10, "duration": 22.5}]

    raw_laps = [
        # Stint 1 (Laps 1-10)
        {"lap_number": 1, "lap_duration": 92.0, "is_pit_out_lap": False},   # Exclude: Lap 1
        {"lap_number": 2, "lap_duration": 85.0, "is_pit_out_lap": False},   # Clean
        {"lap_number": 3, "lap_duration": 85.1, "is_pit_out_lap": False},   # Clean
        {"lap_number": 4, "lap_duration": 85.2, "is_pit_out_lap": False},   # Clean
        {"lap_number": 5, "lap_duration": 120.0, "is_pit_out_lap": False},  # Exclude: Outlier > 107% (SC/traffic)
        {"lap_number": 6, "lap_duration": 85.3, "is_pit_out_lap": False},   # Clean
        {"lap_number": 7, "lap_duration": 85.4, "is_pit_out_lap": False},   # Clean
        {"lap_number": 8, "lap_duration": None, "is_pit_out_lap": False},   # Exclude: Null duration
        {"lap_number": 9, "lap_duration": 85.5, "is_pit_out_lap": False},   # Clean
        {"lap_number": 10, "lap_duration": 89.0, "is_pit_out_lap": False},  # Exclude: Pit-in lap

        # Stint 2 (Laps 11-20)
        {"lap_number": 11, "lap_duration": 105.0, "is_pit_out_lap": True},  # Exclude: Pit-out lap
        {"lap_number": 12, "lap_duration": 84.0, "is_pit_out_lap": False},  # Clean
        {"lap_number": 13, "lap_duration": 84.1, "is_pit_out_lap": False},  # Clean
        {"lap_number": 14, "lap_duration": 84.2, "is_pit_out_lap": False},  # Clean
        {"lap_number": 15, "lap_duration": 84.3, "is_pit_out_lap": False},  # Clean
        {"lap_number": 16, "lap_duration": 84.4, "is_pit_out_lap": False},  # Clean
        {"lap_number": 17, "lap_duration": 84.5, "is_pit_out_lap": False},  # Clean
        {"lap_number": 18, "lap_duration": 84.6, "is_pit_out_lap": False},  # Clean
        {"lap_number": 19, "lap_duration": 84.7, "is_pit_out_lap": False},  # Clean
        {"lap_number": 20, "lap_duration": 84.8, "is_pit_out_lap": False},  # Clean (final lap of final stint)
    ]

    processed_stints, clean_laps, outliers, pit_numbers = filter_clean_laps_and_compute_deg(
        laps=raw_laps,
        stints=stints,
        pit_stops=pit_stops,
    )

    # 1. Pit stop verification
    assert pit_numbers == [10]

    # 2. Outliers inspection
    outlier_reasons = {o["lap_number"]: o["reason"] for o in outliers}
    assert "Standing Start" in outlier_reasons[1]
    assert "Pace Outlier" in outlier_reasons[5]
    assert "Invalid/Null" in outlier_reasons[8]
    assert "Pit-In" in outlier_reasons[10]
    assert "Pit-Out" in outlier_reasons[11]

    # 3. Clean laps count
    clean_lap_nums = [c["lap_number"] for c in clean_laps]
    assert clean_lap_nums == [2, 3, 4, 6, 7, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20]

    # 4. Stint degradation slope verification
    stint_1 = processed_stints[0]
    assert stint_1["clean_lap_count"] == 6
    assert stint_1["compound"] == "MEDIUM"
    # Laps 2, 3, 4, 6, 7, 9 pace is 85.0, 85.1, 85.2, 85.3, 85.4, 85.5 -> slope is ~0.071 s/lap
    assert stint_1["deg_slope_sec_per_lap"] == pytest.approx(0.071, abs=0.01)
    assert stint_1["avg_clean_pace_s"] == pytest.approx(85.25, abs=0.05)
    assert stint_1["fastest_clean_lap_s"] == pytest.approx(85.0, abs=0.01)

    stint_2 = processed_stints[1]
    assert stint_2["clean_lap_count"] == 9
    assert stint_2["compound"] == "HARD"
    # Laps 12 to 20 incrementing by 0.1s/lap exactly
    assert stint_2["deg_slope_sec_per_lap"] == pytest.approx(0.1, abs=0.01)


def test_analyze_tyre_stints_monza_2024_lec_vs_pia():
    """
    Integration test on real cached OpenF1 data for 2024 Italian GP Race (Session 9590).
    Compares Charles Leclerc (16, 1-stop) vs Oscar Piastri (81, 2-stop).
    """
    res = analyze_tyre_stints(
        year=2024,
        grand_prix="Italian Grand Prix",
        driver1="LEC",
        driver2="PIA",
        session_type="Race",
    )

    metrics = res["metrics"]
    chart = res["chart"]
    spec = chart["spec"]
    trace = res["trace"]

    # 1. Metrics validation
    assert "LEC" in metrics
    assert "PIA" in metrics

    lec_m = metrics["LEC"]
    pia_m = metrics["PIA"]

    # Leclerc 1-stop: 2 stints (Medium -> Hard), 1 pit stop on lap 15
    assert len(lec_m["stints"]) == 2
    assert lec_m["pit_stops"] == [15]
    assert lec_m["stints"][0]["compound"] == "MEDIUM"
    assert lec_m["stints"][0]["clean_laps"] == 13
    assert lec_m["stints"][0]["deg_slope_sec_per_lap"] == pytest.approx(0.020, abs=0.005)

    assert lec_m["stints"][1]["compound"] == "HARD"
    assert lec_m["stints"][1]["clean_laps"] == 37
    # Fuel burn advantage at Monza overcame degradation on the Hard compound
    assert lec_m["stints"][1]["deg_slope_sec_per_lap"] < 0.0

    # Piastri 2-stop: 3 stints (Medium -> Hard -> Hard), 2 pit stops on laps 16 and 38
    assert len(pia_m["stints"]) == 3
    assert pia_m["pit_stops"] == [16, 38]
    assert pia_m["stints"][0]["compound"] == "MEDIUM"
    assert pia_m["stints"][1]["compound"] == "HARD"
    assert pia_m["stints"][2]["compound"] == "HARD"

    # Piastri Stint 1 has 14 clean laps
    assert pia_m["stints"][0]["clean_laps"] == 14
    # Piastri Stint 2 has 20 clean laps
    assert pia_m["stints"][1]["clean_laps"] == 20
    # Piastri Stint 3 has 14 clean laps
    assert pia_m["stints"][2]["clean_laps"] == 14

    # 2. Chart spec validation
    assert chart["chart_type"] == "tyre_degradation"
    assert spec["chart_type"] == "tyre_degradation"
    assert spec["layout"]["paper_bgcolor"] == "#0B0F17"
    assert spec["layout"]["plot_bgcolor"] == "#0B0F17"

    # Must contain traces for clean lap scatter and stint bars
    trace_types = [t.get("type", "scatter") for t in spec["data"]]
    assert "scatter" in trace_types
    assert "bar" in trace_types

    # 3. Engineering trace validation
    assert trace["data_domain"] == "telemetry"
    assert trace["confidence"] == 1.0
    s_params = trace["strategy_params"]
    assert s_params["year"] == 2024
    assert s_params["session_key"] == 9590
    assert s_params["stint_counts"]["LEC"] == 2
    assert s_params["stint_counts"]["PIA"] == 3
    assert s_params["pit_stop_laps"]["LEC"] == [15]
    assert s_params["pit_stop_laps"]["PIA"] == [16, 38]


def test_era_boundary_enforcement():
    """
    Validates that requesting pre-2023 telemetry raises ValueError instructing historical query.
    """
    with pytest.raises(ValueError) as excinfo:
        analyze_tyre_stints(
            year=2021,
            grand_prix="Abu Dhabi Grand Prix",
            driver1="VER",
            driver2="HAM",
        )
    assert "2023–present" in str(excinfo.value)
    assert "DuckDB" in str(excinfo.value)


def test_missing_driver_handling():
    """
    Validates that requesting a non-existent driver in a valid session raises clear ValueError.
    """
    with pytest.raises(ValueError) as excinfo:
        analyze_tyre_stints(
            year=2024,
            grand_prix="Italian Grand Prix",
            driver1="NONEXISTENT_DRIVER_XYZ",
            driver2="LEC",
        )
    assert "not found" in str(excinfo.value).lower()


def test_format_trace_event_strategy_unpacking():
    """
    Regression test for format_trace_event(**stint_result['trace']).
    Verifies strategy_params (and any arbitrary extra keyword arguments)
    unpack cleanly into trace SSE event with zero TypeError.
    """
    res = analyze_tyre_stints(
        year=2024,
        grand_prix="Italian Grand Prix",
        driver1="LEC",
        driver2="PIA",
        session_type="Race",
    )

    # 1. Direct unpacking of tool trace dict
    trace_event = format_trace_event(**res["trace"])
    assert "event: trace\n" in trace_event
    assert '"data_domain": "telemetry"' in trace_event
    assert '"strategy_params"' in trace_event
    assert '"session_key": 9590' in trace_event

    # 2. Unpacking with future domain-specific kwargs (**extra)
    future_trace_event = format_trace_event(
        **res["trace"],
        position_evolution_params={"sample": 123},
        future_phase_field="valid",
    )
    assert "event: trace\n" in future_trace_event
    assert '"position_evolution_params"' in future_trace_event
    assert '"future_phase_field": "valid"' in future_trace_event


def test_orchestrator_stream_query_tyre_stint_strategy():
    """
    Regression test exercising the tyre-stint branch of orchestrator.stream_query.
    Verifies that status, trace, chart, text, and done SSE events emit cleanly
    with zero TypeError.
    """
    async def _run():
        orchestrator = RaceEngineerOrchestrator()
        session = ConversationSession(session_id="test-strategy-stream-regression", user_id="test_user")

        events = []
        async for event_str in orchestrator.stream_query(
            user_message="Compare Leclerc vs Piastri tyre degradation and stint strategy at 2024 Italian GP",
            session=session,
        ):
            events.append(event_str)

        full_stream = "".join(events)

        # Verify event types are emitted
        assert "event: status\n" in full_stream
        assert "event: trace\n" in full_stream
        assert "event: chart\n" in full_stream
        assert "event: text\n" in full_stream
        assert "event: done\n" in full_stream

        # Verify payload elements
        assert '"strategy_params"' in full_stream
        assert '"chart_type": "tyre_degradation"' in full_stream
        assert "LEC" in full_stream
        assert "PIA" in full_stream

    asyncio.run(_run())


def test_chat_stream_endpoint_tyre_stint_strategy():
    """
    End-to-end regression test for POST /api/chat/stream with tyre stint query.
    Verifies HTTP 200 and all SSE frames emit cleanly with zero TypeError.
    """
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/stream",
            json={"message": "Show tyre degradation and race pace for Leclerc at Monza 2024"},
        )
        assert response.status_code == 200
        text = response.text

        assert "event: session\n" in text
        assert "event: status\n" in text
        assert "event: trace\n" in text
        assert "event: chart\n" in text
        assert "event: text\n" in text
        assert "event: done\n" in text
        assert "strategy_params" in text
        assert "tyre_degradation" in text
        assert "LEC" in text


def test_back_to_back_tyre_queries_isolation():
    """
    Validates driver inheritance, single-driver support, and cache key isolation across
    3 sequential back-to-back queries on the same ConversationSession:
    1. 'Compare Leclerc vs Piastri tyre degradation at 2024 Italian GP'
    2. 'Show tyre degradation and race pace for Leclerc at Monza 2024'
    3. 'Compare Verstappen and Sainz tyre degradation at 2024 Bahrain GP'

    Verifies:
    - All 3 return distinct Plotly figures (different titles / data).
    - Query 2 contains ONLY Leclerc traces (no Piastri traces or metadata).
    - chart.metadata.drivers accurately reflects requested drivers for each query.
    - Status, trace, chart, text, and done frames are cleanly streamed.
    """
    async def _run():
        import json
        orchestrator = RaceEngineerOrchestrator()
        session = ConversationSession(session_id="test-back-to-back-isolation", user_id="test_user")

        async def execute_query(user_msg: str):
            chart_event_data = None
            trace_event_data = None
            async for event_str in orchestrator.stream_query(user_message=user_msg, session=session):
                for line in event_str.split("\n"):
                    if line.startswith("data: ") and '"chart_type"' in line:
                        chart_event_data = json.loads(line[6:])
                    elif line.startswith("data: ") and '"data_domain"' in line:
                        trace_event_data = json.loads(line[6:])
            return chart_event_data, trace_event_data

        # Query 1: LEC vs PIA at Monza
        c1, t1 = await execute_query("Compare Leclerc vs Piastri tyre degradation at 2024 Italian GP")
        assert c1 is not None, "Query 1 did not emit chart"
        spec1 = c1["spec"]
        meta1 = c1.get("metadata") or spec1.get("metadata", {})
        d_codes1 = [d["code"] if isinstance(d, dict) else d for d in meta1.get("drivers", [])]
        assert set(d_codes1) == {"LEC", "PIA"}, f"Expected ['LEC', 'PIA'], got {d_codes1}"

        # Query 2: Solo Leclerc at Monza (MUST NOT inherit Piastri!)
        c2, t2 = await execute_query("Show tyre degradation and race pace for Leclerc at Monza 2024")
        assert c2 is not None, "Query 2 did not emit chart"
        spec2 = c2["spec"]
        meta2 = c2.get("metadata") or spec2.get("metadata", {})
        d_codes2 = [d["code"] if isinstance(d, dict) else d for d in meta2.get("drivers", [])]
        assert d_codes2 == ["LEC"], f"Expected ONLY ['LEC'], got {d_codes2}"
        # Ensure Plotly traces in spec2 only belong to LEC
        trace_names2 = [tr.get("name", "") for tr in spec2.get("data", [])]
        for tr_name in trace_names2:
            assert "PIA" not in tr_name, f"Piastri trace found in solo Leclerc chart: {tr_name}"
            assert "Piastri" not in tr_name, f"Piastri trace found in solo Leclerc chart: {tr_name}"

        # Query 3: VER vs SAI at Bahrain
        c3, t3 = await execute_query("Compare Verstappen and Sainz tyre degradation at 2024 Bahrain GP")
        assert c3 is not None, "Query 3 did not emit chart"
        spec3 = c3["spec"]
        meta3 = c3.get("metadata") or spec3.get("metadata", {})
        d_codes3 = [d["code"] if isinstance(d, dict) else d for d in meta3.get("drivers", [])]
        assert set(d_codes3) == {"VER", "SAI"}, f"Expected ['VER', 'SAI'], got {d_codes3}"

        # Verify all 3 figures are distinct
        assert c1["caption"] != c2["caption"]
        assert c2["caption"] != c3["caption"]
        assert c1["caption"] != c3["caption"]
        assert spec1["data"] != spec2["data"]
        assert spec2["data"] != spec3["data"]
        assert spec1["data"] != spec3["data"]

    asyncio.run(_run())


