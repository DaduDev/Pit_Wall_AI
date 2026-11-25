"""
Corner-by-Corner Telemetry Comparison Tool for PitWall AI.
Single coarse-grained ADK tool that:
- Resolves drivers, circuit, and corner (by turn number or nickname)
- Loads aligned FastF1/cached telemetry laps
- Resamples both drivers onto an identical 1-meter spatial grid across ±200m of the apex
- Computes all 5 corner metrics:
  1. Braking point delta (meters)
  2. Apex minimum speed (km/h)
  3. Lowest gear (gear)
  4. Full-throttle pickup (meters)
  5. Corner time delta (seconds, zeroed at corner entry)
- Builds both the 5-panel synchronized Plotly figure and the zoomed GPS track mini-map figure
- Returns structured metrics + charts + trace in ONE call
"""

import logging
import time
from typing import Any, Dict, Optional, Tuple
import numpy as np
from backend.app.data.duckdb_manager import get_duckdb_manager
from backend.app.data.entity_resolver import EntityResolver, resolve_corner
from backend.app.agent.tools.telemetry import (
    interpolate_to_distance_grid,
    load_driver_lap,
)
from backend.app.charts.telemetry_charts import (
    build_corner_comparison_figure,
    build_corner_minimap_figure,
)
from backend.app.charts.plotly_theme import resolve_team_color, get_driver_trace_styles

logger = logging.getLogger(__name__)


def compute_corner_metrics(
    grid: np.ndarray,
    data_a: Dict[str, np.ndarray],
    data_b: Dict[str, np.ndarray],
    apex_dist: float,
) -> Dict[str, Any]:
    """
    Computes the 5 corner metrics across the ±200m window:
    1. braking_point_delta (meters): difference where Brake >= 10%
    2. apex_min_speed (km/h): min speed within ±50m of apex
    3. lowest_gear: minimum nGear in window
    4. full_throttle_pickup (meters): distance where Throttle >= 95% post-apex
    5. corner_time_delta (seconds): time difference through the window
    """
    # 1. Braking point (entry zone: dist <= apex_dist)
    entry_mask = grid <= apex_dist
    brakes_a = data_a["Brake"][entry_mask]
    brakes_b = data_b["Brake"][entry_mask]
    grid_entry = grid[entry_mask]

    bp_idx_a = np.where(brakes_a >= 10.0)[0]
    bp_idx_b = np.where(brakes_b >= 10.0)[0]

    bp_dist_a = float(grid_entry[bp_idx_a[0]]) if len(bp_idx_a) > 0 else float(grid_entry[0])
    bp_dist_b = float(grid_entry[bp_idx_b[0]]) if len(bp_idx_b) > 0 else float(grid_entry[0])
    braking_point_delta = round(bp_dist_b - bp_dist_a, 1)

    # 2. Apex min speed (within ±50m of apex)
    apex_mask = (grid >= apex_dist - 50.0) & (grid <= apex_dist + 50.0)
    if not np.any(apex_mask):
        apex_mask = np.ones_like(grid, dtype=bool)

    min_speed_a = round(float(np.min(data_a["Speed"][apex_mask])), 1)
    min_speed_b = round(float(np.min(data_b["Speed"][apex_mask])), 1)

    # 3. Lowest gear in corner window
    lowest_gear_a = int(np.min(data_a["nGear"]))
    lowest_gear_b = int(np.min(data_b["nGear"]))

    # 4. Full throttle pickup (exit zone: dist >= apex_dist)
    exit_mask = grid >= apex_dist
    throttle_a = data_a["Throttle"][exit_mask]
    throttle_b = data_b["Throttle"][exit_mask]
    grid_exit = grid[exit_mask]

    th_idx_a = np.where(throttle_a >= 95.0)[0]
    th_idx_b = np.where(throttle_b >= 95.0)[0]

    pickup_a = float(grid_exit[th_idx_a[0]]) if len(th_idx_a) > 0 else float(grid_exit[-1])
    pickup_b = float(grid_exit[th_idx_b[0]]) if len(th_idx_b) > 0 else float(grid_exit[-1])
    throttle_pickup_delta = round(pickup_b - pickup_a, 1)

    # 5. Corner time delta through the slice
    time_a_start = data_a["Time"][0]
    time_a_end = data_a["Time"][-1]
    time_b_start = data_b["Time"][0]
    time_b_end = data_b["Time"][-1]

    total_time_a = time_a_end - time_a_start
    total_time_b = time_b_end - time_b_start
    corner_time_delta = round(total_time_b - total_time_a, 3)

    return {
        "braking_point_delta_m": braking_point_delta,
        "driver_a_braking_m": round(bp_dist_a, 1),
        "driver_b_braking_m": round(bp_dist_b, 1),
        "apex_min_speed_kph": {
            "driver_a": min_speed_a,
            "driver_b": min_speed_b,
            "delta": round(min_speed_b - min_speed_a, 1),
        },
        "lowest_gear": {
            "driver_a": lowest_gear_a,
            "driver_b": lowest_gear_b,
        },
        "full_throttle_pickup_m": throttle_pickup_delta,
        "driver_a_pickup_m": round(pickup_a, 1),
        "driver_b_pickup_m": round(pickup_b, 1),
        "corner_time_delta_s": corner_time_delta,
        "total_corner_time_a_s": round(total_time_a, 3),
        "total_corner_time_b_s": round(total_time_b, 3),
    }


def compare_corner_telemetry(
    year: int,
    grand_prix: str,
    corner: str,
    driver1: str,
    driver2: str,
    session_type: str = "Q",
    lap_number_1: Optional[int] = None,
    lap_number_2: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Executes corner telemetry comparison between two drivers.
    Returns:
    - metrics: computed 5 corner metrics
    - metadata: session and driver metadata
    - chart: multi-panel 5-row Plotly JSON figure
    - minimap: zoomed GPS mini-map Plotly JSON figure
    - trace: Engineering Trace dictionary
    """
    t_start = time.perf_counter()

    # 0. Enforce era boundary before fetching telemetry
    if year < 2023:
        raise ValueError(
            f"Car sensor telemetry (ECU speed, throttle, brake, gear) is digitally available for 2023–present via the OpenF1 REST API. "
            f"For the {year} {grand_prix}, car sensor telemetry is not available, but lap-by-lap pace, sector times, and finishing classifications are fully accessible in Historical Analytics via DuckDB."
        )

    # 1. Resolve Driver and Circuit Entities
    resolver = EntityResolver()
    res_d1 = resolver.resolve_driver(driver1)
    res_d2 = resolver.resolve_driver(driver2)
    res_circ = resolver.resolve_circuit(grand_prix)

    code_1 = res_d1["code"] if res_d1 and res_d1.get("code") else driver1.upper()
    code_2 = res_d2["code"] if res_d2 and res_d2.get("code") else driver2.upper()
    circuit_key = res_circ["circuitRef"] if res_circ else grand_prix.lower()

    # 2. Resolve Corner Reference
    corner_info = resolve_corner(circuit_key, corner)
    if not corner_info or corner_info.get("distance_m") is None:
        raise ValueError(
            f"Corner '{corner}' not recognized for {grand_prix}. "
            f"Please specify a recognized corner name or turn number (e.g. Turn 1, Copse, Eau Rouge)."
        )

    apex_dist = float(corner_info["distance_m"])

    # 3. Load Laps for both drivers
    lap_a = load_driver_lap(
        year=year,
        grand_prix=grand_prix,
        driver_code=code_1,
        session_type=session_type,
        lap_number=lap_number_1,
    )
    lap_b = load_driver_lap(
        year=year,
        grand_prix=grand_prix,
        driver_code=code_2,
        session_type=session_type,
        lap_number=lap_number_2,
    )

    df_a = lap_a["telemetry"]
    df_b = lap_b["telemetry"]
    meta_a = lap_a["metadata"]
    meta_b = lap_b["metadata"]

    # 4. Define 1-meter spatial distance grid (±200m around apex)
    max_dist = min(df_a["Distance"].max(), df_b["Distance"].max())
    d_start = max(0.0, apex_dist - 200.0)
    d_end = min(float(max_dist), apex_dist + 200.0)

    grid = np.arange(d_start, d_end + 1.0, 1.0)

    # 5. Interpolate both drivers onto the exact 1-meter grid
    interp_a = interpolate_to_distance_grid(df_a, grid)
    interp_b = interpolate_to_distance_grid(df_b, grid)

    # 6. Compute corner time delta trace (zeroed at corner entry)
    time_a = interp_a["Time"]
    time_b = interp_b["Time"]
    delta_trace = (time_b - time_b[0]) - (time_a - time_a[0])

    # 7. Compute the 5 Corner Metrics
    metrics = compute_corner_metrics(grid, interp_a, interp_b, apex_dist)

    # 8. Build Plotly Figures
    fig_comparison = build_corner_comparison_figure(
        grid_distance=grid,
        data_a=interp_a,
        data_b=interp_b,
        delta_trace=delta_trace,
        meta_a=meta_a,
        meta_b=meta_b,
        corner_info=corner_info,
    )

    fig_minimap = build_corner_minimap_figure(
        grid_distance=grid,
        data_a=interp_a,
        data_b=interp_b,
        meta_a=meta_a,
        meta_b=meta_b,
        corner_info=corner_info,
    )

    color_1 = resolve_team_color(meta_a.get("team", code_1))
    color_2 = resolve_team_color(meta_b.get("team", code_2))
    style_1, style_2 = get_driver_trace_styles(color_1, color_2)

    corner_nick = corner_info.get("nickname") or f"Turn {corner_info.get('turn_number', '')}"
    turn_num = corner_info.get("turn_number")
    mode_label = f"{corner_nick} • Turn {turn_num}" if turn_num and str(turn_num) not in corner_nick else corner_nick

    standardized_drivers = [
        {
            "code": code_1,
            "name": meta_a.get("team", code_1),
            "color": style_1["color"],
            "compound": meta_a.get("compound"),
        },
        {
            "code": code_2,
            "name": meta_b.get("team", code_2),
            "color": style_2["color"],
            "compound": meta_b.get("compound"),
        },
    ]

    standardized_metadata = {
        "domain": "telemetry",
        "year": year,
        "grand_prix": meta_a.get("event_name", grand_prix),
        "session_name": session_type,
        "mode_label": mode_label,
        "drivers": standardized_drivers,
        "track_status": "DRY",
        "event_name": meta_a.get("event_name", grand_prix),
        "session_type": session_type,
        "turn_number": turn_num,
        "corner_nickname": corner_info.get("nickname"),
    }
    fig_comparison["metadata"] = standardized_metadata
    fig_minimap["metadata"] = standardized_metadata

    exec_time_ms = round((time.perf_counter() - t_start) * 1000, 2)

    # 9. Engineering Trace Payload
    trace_payload = {
        "data_domain": "telemetry",
        "execution_time_ms": exec_time_ms,
        "row_count": len(grid),
        "telemetry_params": {
            "year": year,
            "grand_prix": meta_a["event_name"],
            "session_type": session_type,
            "drivers": [code_1, code_2],
            "turn_number": corner_info.get("turn_number"),
            "corner_nickname": corner_info.get("nickname"),
            "slice_range_m": [d_start, d_end],
            "apex_distance_m": apex_dist,
        },
        "interpolated_points": len(grid),
        "confidence": 1.0,
        "notes": f"Interpolated 1-meter spatial grid across {int(d_end - d_start)}m window via FastF1/NumPy.",
    }

    return {
        "success": True,
        "metrics": metrics,
        "metadata": {
            "driver_a": meta_a,
            "driver_b": meta_b,
            "corner": corner_info,
        },
        "chart": {
            "chart_type": "corner_comparison",
            "spec": fig_comparison,
            "metadata": standardized_metadata,
            "caption": f"Telemetry Comparison: {code_1} vs {code_2} — {corner_info.get('nickname', '')}",
        },
        "minimap": {
            "chart_type": "track_minimap",
            "spec": fig_minimap,
            "metadata": standardized_metadata,
            "caption": f"GPS Track Mini-Map — {corner_info.get('nickname', '')}",
        },
        "trace": trace_payload,
    }
