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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from backend.app.config import settings
from backend.app.data.fastf1_cache import init_fastf1_cache, load_session_with_retry
from backend.app.data.openf1_client import get_openf1_client

logger = logging.getLogger(__name__)


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
    Loads verified fixture data from data/fastf1_cache/fixture_2024_silverstone_q.json
    when FastF1 requires unauthenticated live timing or in offline testing.
    """
    fixture_path = settings.FASTF1_CACHE_DIR / "fixture_2024_silverstone_q.json"
    if not fixture_path.exists():
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
