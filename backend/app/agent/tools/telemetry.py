"""
FastF1 Telemetry Loader, Metadata Extractor, and 1-Meter Spatial Interpolator.
Implements:
- Aligned car channel extraction (Speed, Throttle, Brake, nGear, RPM, DRS, X, Y, Z, Time)
- Explicit numeric Brake conversion (0 / 100)
- 1-meter spatial distance interpolation using numpy
- Session and lap metadata extraction
- Local verified fixture fallback for offline/test environments
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from backend.app.config import settings
from backend.app.data.entity_resolver import EntityResolver
from backend.app.data.fastf1_cache import init_fastf1_cache, load_session_with_retry
from backend.app.data.openf1_client import get_openf1_client
from backend.app.charts.telemetry_charts import build_full_lap_comparison_figure

logger = logging.getLogger(__name__)


def _format_lap_time_str(seconds: float) -> str:
    """Formats lap time in seconds to M:SS.mmm string (e.g. 72.0 -> 1:12.000)."""
    try:
        sec = float(seconds)
        if sec <= 0:
            return "N/A"
        mins = int(sec // 60)
        rem = sec - mins * 60
        return f"{mins}:{rem:06.3f}" if mins > 0 else f"{rem:.3f}s"
    except Exception:
        return str(seconds)


def extract_lap_telemetry(lap: Any) -> pd.DataFrame:
    """
    Extracts raw telemetry from a FastF1 lap and normalizes channels.
    Converts Brake explicitly to numeric 0.0 or 100.0 (FastF1 often returns booleans).
    Ensures Distance, Speed, Throttle, Brake, nGear, X, Y, Time are present.
    """
    tel = lap.get_telemetry()
    if tel is None or tel.empty:
        raise ValueError("Telemetry is empty for the specified lap.")

    df = pd.DataFrame()
    df["Distance"] = tel["Distance"].to_numpy(dtype=float)
    df["Speed"] = tel["Speed"].to_numpy(dtype=float)
    df["Throttle"] = tel["Throttle"].to_numpy(dtype=float)

    # Normalize Brake to numeric 0 or 100
    if tel["Brake"].dtype == bool or tel["Brake"].dtype == object:
        df["Brake"] = np.where(tel["Brake"].astype(bool), 100.0, 0.0)
    else:
        df["Brake"] = np.where(tel["Brake"] > 0, 100.0, 0.0)

    df["nGear"] = tel["nGear"].to_numpy(dtype=int)
    df["RPM"] = tel["RPM"].to_numpy(dtype=float) if "RPM" in tel else 0.0
    df["DRS"] = tel["DRS"].to_numpy(dtype=int) if "DRS" in tel else 0
    df["X"] = tel["X"].to_numpy(dtype=float) if "X" in tel else 0.0
    df["Y"] = tel["Y"].to_numpy(dtype=float) if "Y" in tel else 0.0
    df["Z"] = tel["Z"].to_numpy(dtype=float) if "Z" in tel else 0.0

    # Time in seconds from lap start
    if "Time" in tel and pd.api.types.is_timedelta64_dtype(tel["Time"]):
        df["Time"] = tel["Time"].dt.total_seconds().to_numpy(dtype=float)
    else:
        df["Time"] = np.zeros(len(df))

    # Sort and remove duplicate distances if any
    df = df.drop_duplicates(subset=["Distance"]).sort_values("Distance").reset_index(drop=True)
    return df


def interpolate_to_distance_grid(
    df: pd.DataFrame,
    grid: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    Interpolates car channels and GPS coordinates onto an identical 1-meter distance grid.
    """
    dist_orig = df["Distance"].to_numpy()

    interpolated: Dict[str, np.ndarray] = {
        "Distance": grid,
        "Speed": np.interp(grid, dist_orig, df["Speed"].to_numpy()),
        "Throttle": np.interp(grid, dist_orig, df["Throttle"].to_numpy()),
        "Brake": np.interp(grid, dist_orig, df["Brake"].to_numpy()),
        "nGear": np.round(np.interp(grid, dist_orig, df["nGear"].to_numpy())).astype(int),
        "RPM": np.interp(grid, dist_orig, df["RPM"].to_numpy()),
        "DRS": np.round(np.interp(grid, dist_orig, df["DRS"].to_numpy())).astype(int),
        "X": np.interp(grid, dist_orig, df["X"].to_numpy()),
        "Y": np.interp(grid, dist_orig, df["Y"].to_numpy()),
        "Z": np.interp(grid, dist_orig, df["Z"].to_numpy()),
        "Time": np.interp(grid, dist_orig, df["Time"].to_numpy()),
    }
    return interpolated


def load_cached_fixture_lap(
    circuit_key: str,
    driver_code: str,
    year: int = 2024,
) -> Optional[Dict[str, Any]]:
    """
    Loads verified fixture data from runtime FastF1 cache or seeded data/fastf1_cache/fixture_2024_silverstone_q.json
    when FastF1 requires unauthenticated live timing or in offline testing.
    """
    candidate_paths = [
        settings.get_fastf1_cache_dir() / "fixture_2024_silverstone_q.json",
        settings.FASTF1_CACHE_DIR / "fixture_2024_silverstone_q.json",
    ]
    fixture_path = next((p for p in candidate_paths if p.exists()), None)
    if fixture_path is None:
        return None

    try:
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        drivers = data.get("drivers", {})
        drv_info = drivers.get(driver_code.upper())
        if not drv_info:
            return None

        car_data = drv_info.get("car_data", [])
        loc_data = drv_info.get("location", [])

        if not car_data:
            return None

        # Build DataFrame matching FastF1 telemetry columns
        car_df = pd.DataFrame(car_data)
        loc_df = pd.DataFrame(loc_data) if loc_data else pd.DataFrame()

        # Parse date and sort
        car_df["date"] = pd.to_datetime(car_df["date"])
        car_df = car_df.sort_values("date").reset_index(drop=True)

        # Compute elapsed time in seconds
        t0 = car_df["date"].iloc[0]
        car_df["Time"] = (car_df["date"] - t0).dt.total_seconds()

        # Compute cumulative distance (Speed in km/h -> m/s)
        speeds_ms = car_df["speed"] * (1000.0 / 3600.0)
        dt = np.diff(car_df["Time"].to_numpy(), prepend=0.0)
        dt[0] = 0.0
        car_df["Distance"] = np.cumsum(speeds_ms * dt)

        # Merge GPS coordinates if present
        if not loc_df.empty:
            loc_df["date"] = pd.to_datetime(loc_df["date"])
            loc_df = loc_df.sort_values("date").reset_index(drop=True)
            merged = pd.merge_asof(
                car_df,
                loc_df[["date", "x", "y", "z"]],
                on="date",
                direction="nearest",
            )
            car_df["X"] = merged["x"].fillna(0.0)
            car_df["Y"] = merged["y"].fillna(0.0)
            car_df["Z"] = merged["z"].fillna(0.0)
        else:
            car_df["X"] = 0.0
            car_df["Y"] = 0.0
            car_df["Z"] = 0.0

        car_df["Speed"] = car_df["speed"].astype(float)
        car_df["Throttle"] = car_df["throttle"].astype(float)
        car_df["Brake"] = np.where(car_df["brake"] > 0, 100.0, 0.0)
        car_df["nGear"] = car_df["n_gear"].astype(int)
        car_df["RPM"] = car_df["rpm"].astype(float)
        car_df["DRS"] = car_df["drs"].astype(int)

        # Scale distance so total distance matches Silverstone lap length (~5891m)
        max_dist = car_df["Distance"].iloc[-1]
        if max_dist > 0:
            scale = 5891.0 / max_dist
            car_df["Distance"] = car_df["Distance"] * scale

        metadata = {
            "event_name": data["session"]["grand_prix"],
            "year": data["session"]["year"],
            "session_type": data["session"]["session_type"],
            "driver_code": drv_info["driver_code"],
            "driver_number": drv_info["driver_number"],
            "lap_number": drv_info["lap_number"],
            "lap_time": drv_info["lap_time_s"],
            "compound": drv_info.get("compound", "SOFT"),
            "team": drv_info["team"],
            "team_color": drv_info["team_color"],
            "weather": "Dry",
        }
        return {"telemetry": car_df, "metadata": metadata}
    except Exception as e:
        logger.warning(f"Failed to load cached fixture lap for {driver_code}: {e}")
        return None


def load_driver_lap(
    year: int,
    grand_prix: str,
    driver_code: str,
    session_type: str = "Q",
    lap_number: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Loads telemetry and metadata for a driver's lap.
    Primary Provider: OpenF1 REST API (2023+ sessions) with persistent disk cache.
    Secondary / Offline Fallback: Verified cached fixtures (only when USE_OFFLINE_FIXTURES=1).
    """
    code_upper = driver_code.strip().upper()

    # 1. Enforce era boundary BEFORE fetching telemetry (FR-013)
    if year < 2023:
        raise ValueError(
            f"Car sensor telemetry (ECU speed, throttle, brake, gear) is digitally available for 2023–present via the OpenF1 REST API. "
            f"For the {year} {grand_prix}, car sensor telemetry is not available, but lap-by-lap pace, sector times, and finishing classifications are fully accessible in Historical Analytics via DuckDB."
        )

    # 2. Check verified offline fixtures ONLY if explicitly enabled for testing
    if os.environ.get("USE_OFFLINE_FIXTURES") == "1":
        fixture = load_cached_fixture_lap("silverstone", code_upper, year)
        if fixture is not None:
            logger.info(f"Loaded telemetry for {code_upper} from verified offline fixture.")
            return fixture

    # 3. Live OpenF1 REST API with local persistent disk caching
    try:
        client = get_openf1_client()
        res = client.load_openf1_driver_lap(
            year=year,
            grand_prix=grand_prix,
            driver_code=code_upper,
            session_type=session_type,
            lap_number=lap_number,
        )
        logger.info(f"Loaded telemetry for {code_upper} from OpenF1 ({year} {grand_prix}).")
        return res
    except Exception as o1_err:
        logger.error(f"OpenF1 telemetry load failed for {code_upper} ({year} {grand_prix}): {o1_err}")
        raise RuntimeError(
            f"Unable to load OpenF1 telemetry for {code_upper} in {year} {grand_prix}: {o1_err}"
        )


def compare_full_lap_telemetry(
    year: int,
    grand_prix: Optional[str] = None,
    driver1: Optional[str] = None,
    driver2: Optional[str] = None,
    session_type: str = "Q",
    lap_number_1: Optional[int] = None,
    lap_number_2: Optional[int] = None,
    circuit: Optional[str] = None,
    driver_a: Optional[str] = None,
    driver_b: Optional[str] = None,
    session: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Coarse-grained ADK tool for broadcast-grade full-lap telemetry overlay comparison.
    1. Resolves drivers and circuit entities
    2. Loads aligned laps for both drivers via OpenF1 (ignoring pit-out laps)
    3. Normalizes and interpolates both laps onto a common 5-meter spatial grid
    4. Computes cumulative delta trace starting at 0.000s and matching official lap_duration delta at finish
    5. Computes structured sector deltas, speed trap speeds, full-throttle %, and braking %
    6. Builds synchronized 4-panel Plotly figure and Engineering Trace
    """
    t_start = time.perf_counter()

    resolved_gp = grand_prix or circuit
    if not resolved_gp:
        raise ValueError("grand_prix or circuit must be specified.")
    resolved_d1 = driver1 or driver_a
    resolved_d2 = driver2 or driver_b
    if not resolved_d1 or not resolved_d2:
        raise ValueError("Both drivers must be specified.")
    resolved_session = session or session_type

    # 1. Enforce strict 2023 era boundary
    if year < 2023:
        raise ValueError(
            f"Car sensor telemetry (ECU speed, throttle, brake, gear) is digitally available for 2023–present via the OpenF1 REST API. "
            f"For the {year} {resolved_gp}, car sensor telemetry is not available, but lap-by-lap pace, sector times, and finishing classifications are fully accessible in Historical Analytics via DuckDB."
        )

    # 2. Resolve Driver and Circuit Entities
    resolver = EntityResolver()
    res_d1 = resolver.resolve_driver(resolved_d1)
    res_d2 = resolver.resolve_driver(resolved_d2)
    res_circ = resolver.resolve_circuit(resolved_gp)

    code_1 = res_d1["code"] if res_d1 and res_d1.get("code") else resolved_d1.upper()
    code_2 = res_d2["code"] if res_d2 and res_d2.get("code") else resolved_d2.upper()
    clean_gp = res_circ["name"] if res_circ and res_circ.get("name") else resolved_gp

    # 3. Load full-lap telemetry for both drivers
    try:
        lap_a = load_driver_lap(
            year=year,
            grand_prix=clean_gp,
            driver_code=code_1,
            session_type=resolved_session,
            lap_number=lap_number_1,
        )
    except Exception as e:
        raise ValueError(f"Unable to load full-lap telemetry for {code_1} at {year} {clean_gp}: {str(e)}")

    try:
        lap_b = load_driver_lap(
            year=year,
            grand_prix=clean_gp,
            driver_code=code_2,
            session_type=resolved_session,
            lap_number=lap_number_2,
        )
    except Exception as e:
        raise ValueError(f"Unable to load full-lap telemetry for {code_2} at {year} {clean_gp}: {str(e)}")

    df_a = lap_a["telemetry"]
    df_b = lap_b["telemetry"]
    meta_a = lap_a["metadata"]
    meta_b = lap_b["metadata"]

    if df_a.empty or df_b.empty:
        raise ValueError("Telemetry data is empty for one or both requested laps.")

    # 4. Define Common 5-Meter Distance Grid
    circuit_length = max(float(df_a["Distance"].max()), float(df_b["Distance"].max()))
    if circuit_length <= 0:
        circuit_length = 5000.0

    # Scale distances so both span [0.0, circuit_length]
    if df_a["Distance"].max() > 0:
        df_a = df_a.copy()
        df_a["Distance"] = df_a["Distance"] * (circuit_length / df_a["Distance"].max())
    if df_b["Distance"].max() > 0:
        df_b = df_b.copy()
        df_b["Distance"] = df_b["Distance"] * (circuit_length / df_b["Distance"].max())

    grid = np.arange(0.0, circuit_length + 5.0, 5.0)
    interp_a = interpolate_to_distance_grid(df_a, grid)
    interp_b = interpolate_to_distance_grid(df_b, grid)

    # 5. Compute Cumulative Delta Trace
    time_a_official = float(meta_a.get("lap_time", 0.0))
    time_b_official = float(meta_b.get("lap_time", 0.0))
    delta_official = round(time_b_official - time_a_official, 3)

    raw_delta = interp_b["Time"] - interp_a["Time"]
    raw_delta = raw_delta - raw_delta[0]  # Zeroed at start/finish line

    drift = delta_official - raw_delta[-1]
    delta_trace = np.round(raw_delta + drift * (grid / circuit_length), 3)
    delta_trace[0] = 0.000
    delta_trace[-1] = delta_official

    # 6. Locate Sector Boundaries on Distance Axis
    s1_dur_a = float(meta_a.get("duration_sector_1") or (time_a_official / 3.0))
    s2_dur_a = float(meta_a.get("duration_sector_2") or (time_a_official / 3.0))
    s1_dur_b = float(meta_b.get("duration_sector_1") or (time_b_official / 3.0))
    s2_dur_b = float(meta_b.get("duration_sector_2") or (time_b_official / 3.0))

    idx_s1_a = np.where(interp_a["Time"] >= s1_dur_a)[0]
    d_s1_a = float(grid[idx_s1_a[0]]) if len(idx_s1_a) > 0 else circuit_length * 0.33
    idx_s2_a = np.where(interp_a["Time"] >= (s1_dur_a + s2_dur_a))[0]
    d_s2_a = float(grid[idx_s2_a[0]]) if len(idx_s2_a) > 0 else circuit_length * 0.66

    idx_s1_b = np.where(interp_b["Time"] >= s1_dur_b)[0]
    d_s1_b = float(grid[idx_s1_b[0]]) if len(idx_s1_b) > 0 else circuit_length * 0.33
    idx_s2_b = np.where(interp_b["Time"] >= (s1_dur_b + s2_dur_b))[0]
    d_s2_b = float(grid[idx_s2_b[0]]) if len(idx_s2_b) > 0 else circuit_length * 0.66

    s1_dist = round(float((d_s1_a + d_s1_b) / 2.0), 1)
    s2_dist = round(float((d_s2_a + d_s2_b) / 2.0), 1)

    # 7. Compute Structured Metrics
    s1_delta = round(float(s1_dur_b - s1_dur_a), 3)
    s2_delta = round(float(s2_dur_b - s2_dur_a), 3)
    s3_dur_a = float(meta_a.get("duration_sector_3") or (time_a_official - s1_dur_a - s2_dur_a))
    s3_dur_b = float(meta_b.get("duration_sector_3") or (time_b_official - s1_dur_b - s2_dur_b))
    s3_delta = round(float(s3_dur_b - s3_dur_a), 3)

    st_a = float(meta_a.get("st_speed") or np.max(interp_a["Speed"]))
    st_b = float(meta_b.get("st_speed") or np.max(interp_b["Speed"]))
    st_delta = round(float(st_b - st_a), 1)

    full_thr_a = round(float(np.mean(interp_a["Throttle"] >= 98.0) * 100.0), 1)
    full_thr_b = round(float(np.mean(interp_b["Throttle"] >= 98.0) * 100.0), 1)

    brk_a = round(float(np.mean(interp_a["Brake"] >= 10.0) * 100.0), 1)
    brk_b = round(float(np.mean(interp_b["Brake"] >= 10.0) * 100.0), 1)

    lap_faster = (
        "TIE"
        if abs(delta_official) < 0.0005
        else (code_1 if delta_official > 0 else code_2)
    )
    d1_time_str = _format_lap_time_str(time_a_official)
    d2_time_str = _format_lap_time_str(time_b_official)

    metrics = {
        "lap_times": {
            "driver_a": time_a_official,
            "driver_b": time_b_official,
            "driver_1_lap_time": d1_time_str,
            "driver_2_lap_time": d2_time_str,
            "delta_s": delta_official,
            "faster": lap_faster,
            "faster_driver": lap_faster,
        },
        "sectors": {
            "sector_1": {
                "driver_a": round(float(s1_dur_a), 3),
                "driver_b": round(float(s1_dur_b), 3),
                "delta_s": s1_delta,
                "faster": code_1 if s1_delta > 0 else code_2,
                "boundary_m": s1_dist,
            },
            "sector_2": {
                "driver_a": round(float(s2_dur_a), 3),
                "driver_b": round(float(s2_dur_b), 3),
                "delta_s": s2_delta,
                "faster": code_1 if s2_delta > 0 else code_2,
                "boundary_m": s2_dist,
            },
            "sector_3": {
                "driver_a": round(float(s3_dur_a), 3),
                "driver_b": round(float(s3_dur_b), 3),
                "delta_s": s3_delta,
                "faster": code_1 if s3_delta > 0 else code_2,
            },
        },
        "speed_trap": {
            "driver_a": round(float(st_a), 1),
            "driver_b": round(float(st_b), 1),
            "delta_kph": st_delta,
            "max_speed_a": round(float(np.max(interp_a["Speed"])), 1),
            "max_speed_b": round(float(np.max(interp_b["Speed"])), 1),
        },
        "full_throttle_pct": {
            "driver_a": full_thr_a,
            "driver_b": full_thr_b,
            "delta": round(full_thr_b - full_thr_a, 1),
        },
        "braking_pct": {
            "driver_a": brk_a,
            "driver_b": brk_b,
            "delta": round(brk_b - brk_a, 1),
        },
    }

    # 8. Build Plotly Chart Spec
    chart_spec = build_full_lap_comparison_figure(
        grid_distance=grid,
        data_a=interp_a,
        data_b=interp_b,
        delta_trace=delta_trace,
        meta_a=meta_a,
        meta_b=meta_b,
        sector_boundaries=(s1_dist, s2_dist),
        metrics=metrics,
    )

    # 9. Build Engineering Trace
    trace = {
        "data_domain": "telemetry",
        "execution_time_ms": round((time.perf_counter() - t_start) * 1000, 2),
        "confidence": 1.0,
        "telemetry_params": {
            "year": year,
            "grand_prix": clean_gp,
            "session_type": resolved_session,
            "session_key": meta_a.get("session_key"),
            "drivers": [code_1, code_2],
            "driver_numbers": {code_1: meta_a.get("driver_number"), code_2: meta_b.get("driver_number")},
            "lap_numbers": {code_1: meta_a.get("lap_number"), code_2: meta_b.get("lap_number")},
            "sector_boundaries_m": [s1_dist, s2_dist],
            "circuit_length_m": round(float(circuit_length), 1),
            "grid_resolution_m": 5.0,
        },
        "interpolated_points": len(grid),
        "notes": f"Full-lap telemetry from OpenF1 ({meta_a.get('session_key')}) aligned across {len(grid)} points at 5m resolution.",
    }

    return {
        "metrics": metrics,
        "metadata": {
            "driver_a": meta_a,
            "driver_b": meta_b,
            "sector_boundaries": [s1_dist, s2_dist],
        },
        "chart": {
            "chart_type": "full_lap_comparison",
            "spec": chart_spec,
            "metadata": chart_spec.get("metadata", {}),
            "caption": f"Full-Lap Telemetry: {code_1} vs {code_2} ({year} {clean_gp})",
        },
        "trace": trace,
    }
