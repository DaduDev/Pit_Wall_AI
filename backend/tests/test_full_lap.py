"""
Integration Tests for Full-Lap Telemetry Overlay (Phase 5 / User Story 3).
Validates:
- Full-lap telemetry loading via OpenF1 client and local cache
- 5-meter uniform spatial distance grid alignment across entire lap
- Cumulative time delta trace math: starts at 0.000s and terminates at official lap delta
- Sector 1/2/3 splits and Speed Trap extractions
- Broadcast-grade 4-panel synchronized Plotly HUD figures (#0B0F17)
- Pre-2023 era boundary enforcement (FR-013)
- Missing-lap and unknown driver error handling (T045)
"""

import pytest
import numpy as np
from backend.app.agent.tools.telemetry import compare_full_lap_telemetry


def test_full_lap_monza_2024_ver_vs_nor():
    """
    Validates full-lap telemetry overlay for 2024 Italian GP Qualifying (Norris vs Verstappen).
    Uses real cached OpenF1 session data (session_key 9586).
    """
    result = compare_full_lap_telemetry(
        year=2024,
        circuit="Monza",
        driver_a="NOR",
        driver_b="VER",
        session="Q"
    )

    metrics = result["metrics"]
    meta_a = result["metadata"]["driver_a"]
    meta_b = result["metadata"]["driver_b"]
    chart = result["chart"]
    fig_spec = chart["spec"]
    trace = result["trace"]

    # 1. Driver metadata and lap numbers
    assert meta_a["driver_code"] == "NOR"
    assert meta_a["driver_number"] == 4
    assert meta_a["lap_number"] == 11
    assert meta_a["lap_time"] == pytest.approx(79.327, abs=0.01)

    assert meta_b["driver_code"] == "VER"
    assert meta_b["driver_number"] == 1
    assert meta_b["lap_number"] == 11
    assert meta_b["lap_time"] == pytest.approx(79.662, abs=0.01)

    # 2. Sector splits and delta math
    lap_times = metrics["lap_times"]
    assert lap_times["driver_a"] == pytest.approx(79.327, abs=0.01)
    assert lap_times["driver_b"] == pytest.approx(79.662, abs=0.01)
    assert lap_times["delta_s"] == pytest.approx(0.335, abs=0.01)
    assert lap_times["faster"] == "NOR"

    # Official sector times
    sec = metrics["sectors"]
    assert sec["sector_1"]["driver_a"] == pytest.approx(26.492, abs=0.01)
    assert sec["sector_1"]["driver_b"] == pytest.approx(26.389, abs=0.01)
    assert sec["sector_2"]["driver_a"] == pytest.approx(26.579, abs=0.01)
    assert sec["sector_2"]["driver_b"] == pytest.approx(26.656, abs=0.01)
    assert sec["sector_3"]["driver_a"] == pytest.approx(26.256, abs=0.01)
    assert sec["sector_3"]["driver_b"] == pytest.approx(26.617, abs=0.01)

    # Speed traps and throttle percentages
    st = metrics["speed_trap"]
    assert st["driver_a"] == pytest.approx(346.0, abs=2.0)
    assert st["driver_b"] == pytest.approx(347.0, abs=2.0)
    assert metrics["full_throttle_pct"]["driver_a"] > 60.0
    assert metrics["full_throttle_pct"]["driver_b"] > 60.0
    assert metrics["braking_pct"]["driver_a"] > 5.0
    assert metrics["braking_pct"]["driver_b"] > 5.0

    # 3. Figure validation
    assert chart["chart_type"] == "full_lap_comparison"
    layout = fig_spec["layout"]
    assert layout["paper_bgcolor"] == "#0B0F17"
    assert layout["plot_bgcolor"] == "#0B0F17"
    assert layout["hovermode"] == "x unified"

    # Check sector boundary vertical lines and annotations
    shapes = layout.get("shapes", [])
    assert len(shapes) >= 2  # S1 and S2 dashed lines
    annotations = layout.get("annotations", [])
    banner_texts = [a.get("text", "") for a in annotations]
    assert any("SECTOR 1" in t for t in banner_texts)
    assert any("SECTOR 2" in t for t in banner_texts)
    assert any("SECTOR 3" in t for t in banner_texts)

    # 4. Engineering Trace validation
    assert trace["data_domain"] == "telemetry"
    assert trace["interpolated_points"] > 1000
    assert trace["confidence"] == 1.0
    params = trace["telemetry_params"]
    assert params["session_key"] == 9586
    assert params["driver_numbers"] == {"NOR": 4, "VER": 1}
    assert params["lap_numbers"] == {"NOR": 11, "VER": 11}
    assert len(params["sector_boundaries_m"]) == 2
    assert params["circuit_length_m"] == pytest.approx(5793.0, abs=100.0)


def test_full_lap_cumulative_delta_trace_boundary_conditions():
    """
    Verifies that the aligned cumulative time delta starts exactly at 0.000s
    and reaches the official lap duration delta at the finish line.
    """
    result = compare_full_lap_telemetry(
        year=2024,
        circuit="Monza",
        driver_a="NOR",
        driver_b="VER",
        session="Q"
    )
    chart = result["chart"]
    fig_spec = chart["spec"]
    data = fig_spec["data"]

    # Locate delta trace in Plotly figure (y-axis 2)
    delta_trace = None
    for tr in data:
        if tr.get("yaxis") == "y2":
            delta_trace = tr
            break

    assert delta_trace is not None, "Cumulative delta trace not found in Plotly figure data"
    y_vals = delta_trace["y"]
    x_vals = delta_trace["x"]

    # Start condition: exactly 0.000s at start line
    assert y_vals[0] == pytest.approx(0.000, abs=0.0001)
    assert x_vals[0] == 0.0

    # Finish condition: exactly equals official lap delta (VER - NOR = +0.335s)
    expected_delta = result["metrics"]["lap_times"]["delta_s"]
    assert y_vals[-1] == pytest.approx(expected_delta, abs=0.001)

    # Uniform 5-meter grid spacing across lap
    diffs = np.diff(x_vals)
    assert np.allclose(diffs, 5.0, atol=1e-3)


def test_full_lap_spa_2024_ver_vs_lec():
    """
    Validates full-lap telemetry overlay for 2024 Belgian GP Qualifying (VER vs LEC).
    Uses cached OpenF1 session data (session_key 9570).
    """
    result = compare_full_lap_telemetry(
        year=2024,
        circuit="Spa",
        driver_a="VER",
        driver_b="LEC",
        session="Q"
    )

    assert result["metrics"]["lap_times"]["faster"] == "VER"
    assert result["metadata"]["driver_a"]["driver_code"] == "VER"
    assert result["metadata"]["driver_b"]["driver_code"] == "LEC"
    assert result["trace"]["telemetry_params"]["session_key"] == 9570
    assert result["trace"]["telemetry_params"]["circuit_length_m"] == pytest.approx(7004.0, abs=100.0)


def test_full_lap_pre_2023_boundary_rejection():
    """
    Verifies that requesting car sensor telemetry before 2023 raises a ValueError
    explaining OpenF1 availability (FR-013).
    """
    with pytest.raises(ValueError) as excinfo:
        compare_full_lap_telemetry(
            year=2021,
            circuit="Monza",
            driver_a="VER",
            driver_b="HAM",
            session="Q"
        )
    assert "2023–present" in str(excinfo.value)
    assert "DuckDB" in str(excinfo.value)


def test_full_lap_missing_driver_error_handling():
    """
    Verifies that requesting an unknown driver or session with no timed laps raises ValueError (T045).
    """
    with pytest.raises(ValueError) as excinfo:
        compare_full_lap_telemetry(
            year=2024,
            circuit="Monza",
            driver_a="UNKNOWN_DRIVER_XYZ",
            driver_b="NOR",
            session="Q"
        )
    assert "UNKNOWN_DRIVER_XYZ" in str(excinfo.value)


def test_consecutive_circuit_resolution_monza_then_montreal():
    """
    Regression Test for Bug 2: Circuit Resolution & Session Cache Isolation.
    Executes a 2024 Italian GP Qualifying comparison (NOR vs VER) in Turn 1,
    followed immediately by a 2024 Canadian GP Qualifying comparison (RUS vs VER) in Turn 2.
    Asserts:
    - Turn 1 resolves to Monza (OpenF1 session_key 9586) with ~79.3s (1:19.4) lap times.
    - Turn 2 resolves to Montreal (OpenF1 session_key 9527) with ~71.7s (1:11.7) lap times.
    - Two distinct OpenF1 session_keys are used.
    - Montreal does NOT inherit Monza.
    """
    # Turn 1: 2024 Italian GP Qualifying
    res_monza = compare_full_lap_telemetry(
        year=2024,
        grand_prix="Italian GP",
        driver_a="NOR",
        driver_b="VER",
        session="Q",
    )
    assert res_monza["trace"]["telemetry_params"]["session_key"] == 9586
    assert res_monza["metadata"]["driver_a"]["lap_time"] == pytest.approx(79.327, abs=0.5)

    # Turn 2: 2024 Canadian GP Qualifying
    res_canada = compare_full_lap_telemetry(
        year=2024,
        grand_prix="Canadian GP",
        driver_a="RUS",
        driver_b="VER",
        session="Q",
    )
    assert res_canada["trace"]["telemetry_params"]["session_key"] == 9527
    # Montreal lap time ~ 1:11.7 - 1:12.0 (not Monza's 1:19.440)
    assert res_canada["metadata"]["driver_a"]["lap_time"] == pytest.approx(71.742, abs=0.5)
    assert res_canada["metadata"]["driver_b"]["lap_time"] == pytest.approx(72.000, abs=0.5)

    # Validate session key isolation
    assert res_monza["trace"]["telemetry_params"]["session_key"] != res_canada["trace"]["telemetry_params"]["session_key"]


def test_orchestrator_multi_turn_circuit_isolation_monza_then_canada():
    """
    Tests that the orchestrator does NOT inherit 'Monza' from a previous turn
    when a user explicitly asks about 'Canadian GP' in a subsequent turn.
    """
    from backend.app.agent.orchestrator import RaceEngineerOrchestrator
    from backend.app.chat.session import ConversationSession

    orch = RaceEngineerOrchestrator()
    session = ConversationSession(session_id="test_circuit_iso_session", user_id="test_user")

    # Turn 1: user asks for Monza
    intent_1 = orch._parse_full_lap_intent(
        "Overlay Verstappen vs Norris full lap at 2024 Italian GP Qualifying",
        session=session,
    )
    assert intent_1 is not None
    assert intent_1["grand_prix"] == "Monza"
    session.update_entities(year=2024, grand_prix="Monza", drivers=["VER", "NOR"], tool="full_lap")

    # Turn 2: user asks for Canadian GP
    intent_2 = orch._parse_full_lap_intent(
        "Overlay Russell vs Verstappen full lap at 2024 Canadian GP Qualifying",
        session=session,
    )
    assert intent_2 is not None
    assert intent_2["grand_prix"] == "Montreal"
    assert intent_2["grand_prix"] != "Monza"
