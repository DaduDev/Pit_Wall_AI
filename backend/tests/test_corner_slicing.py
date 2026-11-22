"""
Integration Tests for 1-Meter Telemetry Interpolation and ±200m Corner Slicing Math.
Uses verified 2024 British GP Qualifying (Silverstone Copse / Turn 9, VER vs NOR) fixture.
Validates:
- 1-meter spatial interpolation accuracy
- Zeroed corner time delta at entry (0.000s)
- All 5 computed corner metrics
- Teammate collision styling
- Multi-panel Plotly figure structure and GPS mini-map 1:1 aspect ratio
"""

import numpy as np
import pytest
from backend.app.agent.tools.corner_compare import compare_corner_telemetry, compute_corner_metrics
from backend.app.agent.tools.telemetry import (
    extract_lap_telemetry,
    interpolate_to_distance_grid,
    load_driver_lap,
)
from backend.app.charts.plotly_theme import get_driver_trace_styles


def test_telemetry_numeric_brake_normalization():
    """Verifies that boolean or object Brake channels are cleanly converted to numeric 0 or 100."""
    import pandas as pd

    class MockLap:
        def get_telemetry(self):
            return pd.DataFrame({
                "Distance": [10.0, 20.0, 30.0],
                "Speed": [280.0, 275.0, 260.0],
                "Throttle": [100.0, 50.0, 0.0],
                "Brake": [False, True, True],
                "nGear": [8, 7, 7],
                "RPM": [11500, 11200, 10800],
                "DRS": [0, 0, 0],
                "X": [100.0, 110.0, 120.0],
                "Y": [200.0, 210.0, 220.0],
                "Z": [0.0, 0.0, 0.0],
                "Time": pd.to_timedelta([1.0, 1.1, 1.2], unit="s"),
            })

    df = extract_lap_telemetry(MockLap())
    assert df["Brake"].dtype == float or df["Brake"].dtype == np.float64
    assert df["Brake"].tolist() == [0.0, 100.0, 100.0]


def test_1_meter_spatial_interpolation():
    """Verifies that interpolation resamples onto the exact 1-meter distance grid."""
    import pandas as pd

    df = pd.DataFrame({
        "Distance": [100.0, 110.0, 120.0],
        "Speed": [200.0, 250.0, 300.0],
        "Throttle": [50.0, 75.0, 100.0],
        "Brake": [100.0, 0.0, 0.0],
        "nGear": [5, 6, 7],
        "RPM": [10000.0, 11000.0, 12000.0],
        "DRS": [0, 0, 1],
        "X": [10.0, 20.0, 30.0],
        "Y": [10.0, 20.0, 30.0],
        "Z": [0.0, 0.0, 0.0],
        "Time": [10.0, 10.15, 10.3],
    })

    grid = np.arange(100.0, 121.0, 1.0)
    res = interpolate_to_distance_grid(df, grid)

    assert len(res["Distance"]) == 21
    assert res["Distance"][0] == 100.0
    assert res["Distance"][-1] == 120.0
    assert res["Distance"][5] == 105.0
    assert res["Speed"][0] == 200.0
    assert res["Speed"][10] == 250.0  # At 110m
    assert res["Speed"][-1] == 300.0  # At 120m


def test_2024_british_gp_copse_comparison():
    """
    Verifies full corner-by-corner comparison between VER and NOR through Copse
    using the verified 2024 British GP Qualifying data fixture.
    """
    res = compare_corner_telemetry(
        year=2024,
        grand_prix="Silverstone",
        corner="Copse",
        driver1="VER",
        driver2="NOR",
        session_type="Q",
    )

    assert res["success"] is True
    metrics = res["metrics"]
    metadata = res["metadata"]
    chart = res["chart"]
    minimap = res["minimap"]
    trace = res["trace"]

    # 1. Verify Driver and Session Metadata
    assert metadata["driver_a"]["driver_code"] == "VER"
    assert metadata["driver_b"]["driver_code"] == "NOR"
    assert metadata["corner"]["nickname"] == "Copse"
    assert metadata["corner"]["turn_number"] == 9

    # 2. Verify 5 Corner Metrics
    # Braking point delta
    assert "braking_point_delta_m" in metrics
    assert isinstance(metrics["braking_point_delta_m"], (int, float))

    # Apex min speed
    assert "apex_min_speed_kph" in metrics
    assert metrics["apex_min_speed_kph"]["driver_a"] > 150.0  # Copse is high-speed ~240-290 km/h
    assert metrics["apex_min_speed_kph"]["driver_b"] > 150.0

    # Lowest gear
    assert "lowest_gear" in metrics
    assert 6 <= metrics["lowest_gear"]["driver_a"] <= 8
    assert 6 <= metrics["lowest_gear"]["driver_b"] <= 8

    # Full throttle pickup
    assert "full_throttle_pickup_m" in metrics
    assert isinstance(metrics["full_throttle_pickup_m"], (int, float))

    # Corner time delta (in seconds, non-zero total, reasonable threshold < 1.0s)
    assert "corner_time_delta_s" in metrics
    assert abs(metrics["corner_time_delta_s"]) < 1.0

    # 3. Verify Multi-Panel Chart Spec
    spec = chart["spec"]
    assert "data" in spec
    assert "layout" in spec
    # Expect traces for Speed (2), Delta (1), Throttle (2), Brake (2), Gear (2) = at least 9 traces
    assert len(spec["data"]) >= 9
    # Check delta trace starts at exactly 0.0s (first point)
    delta_trace = next(t for t in spec["data"] if "Delta" in t.get("name", ""))
    assert delta_trace["y"][0] == pytest.approx(0.0, abs=1e-4)

    # 4. Verify Mini-Map Figure Spec
    map_spec = minimap["spec"]
    assert "layout" in map_spec
    # Equal aspect ratio
    assert map_spec["layout"]["yaxis"]["scaleanchor"] == "x"
    assert map_spec["layout"]["yaxis"]["scaleratio"] == 1
    # Ticks hidden
    assert map_spec["layout"]["xaxis"]["showticklabels"] is False
    assert map_spec["layout"]["yaxis"]["showticklabels"] is False

    # 5. Verify Engineering Trace
    assert trace["data_domain"] == "telemetry"
    assert trace["telemetry_params"]["drivers"] == ["VER", "NOR"]
    assert trace["telemetry_params"]["turn_number"] == 9
    assert trace["interpolated_points"] > 350


def test_teammate_collision_styling():
    """Verifies that two drivers from the same team are distinguished with dashed line and contrast color."""
    style1, style2 = get_driver_trace_styles("#E80020", "#E80020")
    assert style1["dash"] == "solid"
    assert style2["dash"] == "dash"
    assert style1["color"] != style2["color"]

    # Different teams remain solid
    s1, s2 = get_driver_trace_styles("#3671C6", "#FF8000")
    assert s1["dash"] == "solid"
    assert s2["dash"] == "solid"
    assert s1["color"] == "#3671C6"
    assert s2["color"] == "#FF8000"
