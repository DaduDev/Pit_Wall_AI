"""
Integration Tests for OpenF1 Telemetry Provider & Disk Caching.
Validates:
- Session resolution across multiple circuits (Silverstone 2024, Spa 2024)
- Channel normalization & timestamp alignment (pd.merge_asof)
- 1-meter spatial interpolation and corner slicing across multiple circuits:
  1. 2024 British GP Qualifying (VER vs NOR through Copse / Turn 9)
  2. 2024 Belgian GP Qualifying (VER vs LEC through Eau Rouge / Turn 2)
- Zero authentication requirement (public OpenF1 REST API)
- Persistent disk caching performance (< 500ms for cached sessions)
- Pre-2023 telemetry era boundary error handling (FR-013)
"""

import time
import pytest
from backend.app.data.openf1_client import get_openf1_client
from backend.app.agent.tools.corner_compare import compare_corner_telemetry
from backend.app.agent.tools.telemetry import load_driver_lap


def test_openf1_session_resolution():
    """Verifies that OpenF1 resolves Grand Prix names and session types correctly."""
    client = get_openf1_client()

    # 1. Silverstone 2024 Qualifying
    session_uk = client.resolve_session(2024, "Silverstone", "Q")
    assert session_uk is not None
    assert session_uk["session_key"] == 9554
    assert "Silverstone" in session_uk.get("circuit_short_name", "")

    # 2. Spa 2024 Qualifying
    session_spa = client.resolve_session(2024, "Spa", "Q")
    assert session_spa is not None
    assert session_spa["session_key"] == 9570
    assert "Spa" in session_spa.get("circuit_short_name", "")


def test_openf1_driver_lap_and_channel_alignment():
    """Verifies OpenF1 lap loading, merge_asof timestamp alignment, and distance integration."""
    client = get_openf1_client()
    res = client.load_openf1_driver_lap(2024, "Silverstone", "VER", "Q")

    df = res["telemetry"]
    meta = res["metadata"]

    # Metadata check
    assert meta["driver_code"] == "VER"
    assert meta["driver_number"] == 1
    assert meta["lap_number"] == 23
    assert meta["lap_time"] == pytest.approx(86.203, abs=0.01)
    assert meta["team"] == "Red Bull Racing"
    assert meta["team_color"] == "#3671C6"

    # Channels presence check
    expected_cols = ["Distance", "Speed", "Throttle", "Brake", "nGear", "RPM", "DRS", "X", "Y", "Z", "Time"]
    for col in expected_cols:
        assert col in df.columns

    # Brake numeric normalization (0.0 or 100.0)
    assert set(df["Brake"].unique()).issubset({0.0, 100.0})

    # Distance monotonic integration scaled to circuit length (~5891m)
    assert df["Distance"].iloc[0] == 0.0
    assert df["Distance"].iloc[-1] == pytest.approx(5891.0, abs=10.0)
    assert (df["Distance"].diff().dropna() >= 0).all()

    # Time in seconds
    assert df["Time"].iloc[0] == 0.0
    assert df["Time"].iloc[-1] > 80.0


def test_openf1_corner_comparison_copse_silverstone():
    """
    Verifies full corner telemetry comparison between VER and NOR through Copse
    at 2024 British GP Qualifying using live/cached OpenF1 data.
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

    # Verify drivers & corner
    assert metadata["driver_a"]["driver_code"] == "VER"
    assert metadata["driver_b"]["driver_code"] == "NOR"
    assert metadata["corner"]["nickname"] == "Copse"

    # Verify 5 computed metrics
    assert "braking_point_delta_m" in metrics
    assert "apex_min_speed_kph" in metrics
    assert metrics["apex_min_speed_kph"]["driver_a"] > 200.0  # Copse high speed
    assert metrics["apex_min_speed_kph"]["driver_b"] > 200.0
    assert "lowest_gear" in metrics
    assert 6 <= metrics["lowest_gear"]["driver_a"] <= 8
    assert "full_throttle_pickup_m" in metrics
    assert "corner_time_delta_s" in metrics

    # Verify synchronized chart spec
    assert "data" in chart["spec"]
    assert "layout" in chart["spec"]
    assert len(chart["spec"]["data"]) >= 9

    # Verify minimap
    assert minimap["spec"]["layout"]["yaxis"]["scaleanchor"] == "x"


def test_openf1_second_circuit_spa_eau_rouge():
    """
    Verifies OpenF1 dynamic telemetry loading for a second circuit:
    2024 Belgian GP Qualifying at Spa-Francorchamps (VER vs LEC through Eau Rouge / Turn 2).
    """
    res = compare_corner_telemetry(
        year=2024,
        grand_prix="Spa",
        corner="Eau Rouge",
        driver1="VER",
        driver2="LEC",
        session_type="Q",
    )

    assert res["success"] is True
    metrics = res["metrics"]
    metadata = res["metadata"]

    assert metadata["driver_a"]["driver_code"] == "VER"
    assert metadata["driver_b"]["driver_code"] == "LEC"
    assert metadata["corner"]["nickname"] == "Eau Rouge"
    assert metadata["corner"]["turn_number"] == 2

    # Eau Rouge is iconic high speed uphill sweep: apex speed > 220 km/h in top gear
    assert metrics["apex_min_speed_kph"]["driver_a"] > 200.0
    assert metrics["apex_min_speed_kph"]["driver_b"] > 200.0
    assert metrics["lowest_gear"]["driver_a"] >= 6
    assert metrics["lowest_gear"]["driver_b"] >= 6
    assert isinstance(metrics["corner_time_delta_s"], (int, float))


def test_openf1_disk_caching_instant_response():
    """Verifies that repeat calls load from disk cache in < 500ms."""
    t0 = time.perf_counter()
    res = load_driver_lap(2024, "Silverstone", "VER", "Q")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert res is not None
    assert elapsed_ms < 500.0  # Disk cache is sub-second


def test_pre_2023_telemetry_era_boundary():
    """Verifies that requesting pre-2023 telemetry without cache raises clear era boundary explanation."""
    with pytest.raises(ValueError) as excinfo:
        load_driver_lap(1998, "Monza", "MSC", "Q")

    msg = str(excinfo.value)
    assert "2023" in msg
    assert "OpenF1" in msg
    assert "Historical Analytics" in msg
