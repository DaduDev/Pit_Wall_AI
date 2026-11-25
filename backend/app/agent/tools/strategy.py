"""
PitWall AI Tyre Stint Degradation & Race Strategy Tool.
Implements:
- OpenF1 data fetching for stints, laps, and pit stops (2023-present)
- Clean-lap outlier filtering:
  * Exclude Lap 1 (standing start)
  * Exclude is_pit_out_lap=True
  * Exclude pit-in laps (from pit endpoint and stint transition laps)
  * Exclude null/invalid lap durations
  * Exclude SC/VSC/traffic pace outliers (>107% of stint median clean lap time)
- Deterministic NumPy linear regression for degradation slope (sec/lap)
- 2-subplot synchronized Plotly figure generation
- Engineering trace generation
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.app.charts.strategy_charts import build_tyre_degradation_figure
from backend.app.data.entity_resolver import EntityResolver
from backend.app.data.openf1_client import get_openf1_client

logger = logging.getLogger(__name__)


def filter_clean_laps_and_compute_deg(
    laps: List[Dict[str, Any]],
    stints: List[Dict[str, Any]],
    pit_stops: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[int]]:
    """
    Filters clean race laps per stint and calculates linear pace degradation slope (sec/lap).

    Excludes:
    - Lap 1 (standing start)
    - Pit-out laps (is_pit_out_lap is True)
    - Pit-in laps (laps matching pit_stops or final lap before a stint transition, except last stint)
    - Incomplete/null lap times
    - Outlier laps (>107% of that stint's median clean lap time)

    Returns:
    - processed_stints: list of stint dicts with clean pace, fastest lap, slope, and slope coords
    - all_clean_laps: flattened list of clean lap dicts with compound and tyre age
    - all_outliers: list of excluded lap dicts with failure reason
    - pit_lap_numbers: sorted list of distinct pit stop lap numbers
    """
    pit_lap_set = {
        int(p["lap_number"])
        for p in pit_stops
        if p.get("lap_number") is not None
    }
    pit_lap_numbers = sorted(list(pit_lap_set))

    # Map laps by lap number for fast lookup
    sorted_stints = sorted(stints, key=lambda s: s.get("stint_number", 1))
    max_stint_num = max([s.get("stint_number", 1) for s in sorted_stints]) if sorted_stints else 1

    processed_stints: List[Dict[str, Any]] = []
    all_clean_laps: List[Dict[str, Any]] = []
    all_outliers: List[Dict[str, Any]] = []

    for stint in sorted_stints:
        stint_num = int(stint.get("stint_number", 1))
        lap_start = int(stint.get("lap_start", 1))
        lap_end = int(stint.get("lap_end", lap_start))
        compound = (stint.get("compound") or "UNKNOWN").upper()
        tyre_age_start = int(stint.get("tyre_age_at_start", 0) or 0)

        # Laps belonging to this stint
        stint_raw_laps = [
            l for l in laps
            if l.get("lap_number") is not None and lap_start <= int(l["lap_number"]) <= lap_end
        ]

        candidate_clean: List[Dict[str, Any]] = []
        for l in stint_raw_laps:
            lap_num = int(l["lap_number"])
            dur = l.get("lap_duration")
            is_pit_out = bool(l.get("is_pit_out_lap", False))
            tyre_age = tyre_age_start + (lap_num - lap_start)

            # 1. Null / zero check
            if dur is None or dur <= 0:
                all_outliers.append({
                    "lap_number": lap_num,
                    "lap_duration": 0.0,
                    "stint_number": stint_num,
                    "compound": compound,
                    "reason": "Invalid/Null Lap Time",
                })
                continue

            # 2. Lap 1 standing start check
            if lap_num == 1:
                all_outliers.append({
                    "lap_number": lap_num,
                    "lap_duration": float(dur),
                    "stint_number": stint_num,
                    "compound": compound,
                    "reason": "Standing Start (Lap 1)",
                })
                continue

            # 3. Pit-out lap check
            if is_pit_out:
                all_outliers.append({
                    "lap_number": lap_num,
                    "lap_duration": float(dur),
                    "stint_number": stint_num,
                    "compound": compound,
                    "reason": "Pit-Out Lap",
                })
                continue

            # 4. Pit-in lap check (explicit pit stop or stint transition before next stint)
            if lap_num in pit_lap_set or (stint_num < max_stint_num and lap_num == lap_end):
                all_outliers.append({
                    "lap_number": lap_num,
                    "lap_duration": float(dur),
                    "stint_number": stint_num,
                    "compound": compound,
                    "reason": "Pit-In Lap",
                })
                continue

            # Candidate clean lap
            candidate_clean.append({
                "lap_number": lap_num,
                "lap_duration": float(dur),
                "stint_number": stint_num,
                "compound": compound,
                "tyre_age": tyre_age,
            })

        # 5. Outlier filter: >107% of this stint's median clean lap pace (SC / VSC / traffic)
        final_clean: List[Dict[str, Any]] = []
        if candidate_clean:
            med_pace = float(np.median([c["lap_duration"] for c in candidate_clean]))
            outlier_thresh = 1.07 * med_pace
            for c in candidate_clean:
                if c["lap_duration"] > outlier_thresh:
                    all_outliers.append({
                        "lap_number": c["lap_number"],
                        "lap_duration": c["lap_duration"],
                        "stint_number": stint_num,
                        "compound": compound,
                        "reason": f"Pace Outlier (>107% median {med_pace:.2f}s)",
                    })
                else:
                    final_clean.append(c)

        all_clean_laps.extend(final_clean)

        # 6. Compute degradation linear regression slope if >= 3 clean laps
        times_y = [c["lap_duration"] for c in final_clean]
        laps_x = [c["lap_number"] for c in final_clean]

        if len(laps_x) >= 3:
            slope, intercept = np.polyfit(laps_x, times_y, 1)
            deg_slope = round(float(slope), 3)
            avg_pace = round(float(np.mean(times_y)), 3)
            fastest_lap = round(float(np.min(times_y)), 3)
            slope_coords = (
                [laps_x[0], laps_x[-1]],
                [round(float(slope * laps_x[0] + intercept), 3), round(float(slope * laps_x[-1] + intercept), 3)],
            )
        else:
            deg_slope = 0.0
            avg_pace = round(float(np.mean(times_y)), 3) if times_y else 0.0
            fastest_lap = round(float(np.min(times_y)), 3) if times_y else 0.0
            slope_coords = None

        processed_stints.append({
            "stint_number": stint_num,
            "compound": compound,
            "lap_start": lap_start,
            "lap_end": lap_end,
            "clean_lap_count": len(final_clean),
            "avg_clean_pace_s": avg_pace,
            "fastest_clean_lap_s": fastest_lap,
            "deg_slope_sec_per_lap": deg_slope,
            "slope_coords": slope_coords,
        })

    return processed_stints, all_clean_laps, all_outliers, pit_lap_numbers


def analyze_tyre_stints(
    year: int = 2024,
    grand_prix: str = "Italian Grand Prix",
    drivers: Optional[List[str]] = None,
    driver1: Optional[str] = None,
    driver2: Optional[str] = None,
    session_type: str = "Race",
) -> Dict[str, Any]:
    """
    Coarse-grained ADK tool for Tyre Stint Degradation & Race Pace Strategy.
    - Fetches OpenF1 stints, laps, and pit stops with local caching and rate limiting.
    - Enforces strict 2023+ era boundary.
    - Filters clean laps and computes linear regression degradation slopes.
    - Builds synchronized 2-subplot Plotly figure.
    - Emits Engineering Trace metadata.
    """
    t_start = time.perf_counter()

    # 1. Enforce strict 2023+ era boundary
    if year < 2023:
        raise ValueError(
            f"Tyre stint sensor and degradation data is only available for 2023–present via OpenF1 (requested {year} {grand_prix}). "
            f"For historical races (1950–2022), please query race results or lap-by-lap pace from DuckDB."
        )

    # 2. Resolve Drivers List
    driver_codes_input: List[str] = []
    if drivers:
        if isinstance(drivers, list):
            driver_codes_input.extend([str(d).strip().upper() for d in drivers if str(d).strip()])
        elif isinstance(drivers, str):
            driver_codes_input.extend([d.strip().upper() for d in drivers.split(",") if d.strip()])

    if driver1 and driver1.strip().upper() not in driver_codes_input:
        driver_codes_input.append(driver1.strip().upper())
    if driver2 and driver2.strip().upper() not in driver_codes_input:
        driver_codes_input.append(driver2.strip().upper())

    # 3. Resolve Session via OpenF1
    client = get_openf1_client()
    session_record = client.resolve_session(year=year, grand_prix=grand_prix, session_type=session_type or "Race")
    if not session_record:
        # Retry with session_type="R"
        session_record = client.resolve_session(year=year, grand_prix=grand_prix, session_type="R")

    if not session_record:
        raise ValueError(
            f"Could not locate an OpenF1 session for {year} {grand_prix} ({session_type or 'Race'}). "
            f"Verify the Grand Prix name or year (2023–present only)."
        )

    session_key = int(session_record["session_key"])
    gp_name = session_record.get("country_name") or session_record.get("location") or grand_prix

    # 4. Resolve Driver Numbers from Session
    session_drivers = client.get_drivers(session_key)
    if not session_drivers:
        raise ValueError(f"No driver entries found for OpenF1 session {session_key} ({year} {gp_name}).")

    resolver = EntityResolver()

    # Build driver mapping dictionary from session
    resolved_drivers: Dict[str, Dict[str, Any]] = {}

    if not driver_codes_input:
        # Default to top 2 drivers in session
        for drv_item in session_drivers[:2]:
            code = drv_item.get("name_acronym") or str(drv_item.get("driver_number"))
            resolved_drivers[code] = drv_item
    else:
        for query_drv in driver_codes_input:
            matched_drv = None
            # Direct acronym match
            for drv_item in session_drivers:
                acronym = drv_item.get("name_acronym", "").upper()
                last_name = drv_item.get("last_name", "").upper()
                full_name = drv_item.get("full_name", "").upper()
                broadcast = drv_item.get("broadcast_name", "").upper()

                if query_drv in (acronym, last_name, full_name, broadcast):
                    matched_drv = drv_item
                    break

            # Fuzzy fallback via EntityResolver
            if not matched_drv:
                resolved_code = resolver.resolve_driver(query_drv)
                for drv_item in session_drivers:
                    if drv_item.get("name_acronym", "").upper() == resolved_code:
                        matched_drv = drv_item
                        break

            if not matched_drv:
                raise ValueError(
                    f"Driver '{query_drv}' not found in {year} {gp_name} session. "
                    f"Available drivers: {', '.join([d.get('name_acronym', '') for d in session_drivers if d.get('name_acronym')])}"
                )

            code = matched_drv.get("name_acronym") or str(matched_drv.get("driver_number"))
            resolved_drivers[code] = matched_drv

    # 5. Fetch Stints, Laps, Pit Stops & Compute Degradation
    drivers_data: Dict[str, Dict[str, Any]] = {}
    summary_metrics: Dict[str, Any] = {}

    for drv_code, drv_info in resolved_drivers.items():
        drv_num = int(drv_info["driver_number"])
        team_name = drv_info.get("team_name") or drv_code

        raw_stints = client.get_stints(session_key=session_key, driver_number=drv_num)
        raw_laps = client.get_laps(session_key=session_key, driver_number=drv_num)
        raw_pits = client.get_pit(session_key=session_key, driver_number=drv_num)

        if not raw_stints:
            # If no stints endpoint data, infer single stint from laps
            raw_stints = [{
                "stint_number": 1,
                "driver_number": drv_num,
                "lap_start": 1,
                "lap_end": max([l.get("lap_number", 1) for l in raw_laps]) if raw_laps else 1,
                "compound": "UNKNOWN",
                "tyre_age_at_start": 0,
            }]

        processed_stints, clean_laps, outliers, pit_numbers = filter_clean_laps_and_compute_deg(
            laps=raw_laps,
            stints=raw_stints,
            pit_stops=raw_pits,
        )

        drivers_data[drv_code] = {
            "driver_number": drv_num,
            "team_name": team_name,
            "stints": processed_stints,
            "clean_laps": clean_laps,
            "outliers": outliers,
            "pit_stops": pit_numbers,
        }

        summary_metrics[drv_code] = {
            "driver_number": drv_num,
            "team_name": team_name,
            "pit_stops": pit_numbers,
            "total_clean_laps": len(clean_laps),
            "total_outliers": len(outliers),
            "stints": [
                {
                    "stint_number": s["stint_number"],
                    "compound": s["compound"],
                    "lap_start": s["lap_start"],
                    "lap_end": s["lap_end"],
                    "clean_laps": s["clean_lap_count"],
                    "avg_clean_pace_s": s["avg_clean_pace_s"],
                    "fastest_clean_lap_s": s["fastest_clean_lap_s"],
                    "deg_slope_sec_per_lap": s["deg_slope_sec_per_lap"],
                }
                for s in processed_stints
            ],
        }

    # 6. Build Plotly Chart Spec
    event_metadata = {
        "year": year,
        "grand_prix": gp_name,
        "session_type": session_record.get("session_name", session_type or "Race"),
    }

    chart_spec = build_tyre_degradation_figure(
        drivers_data=drivers_data,
        event_metadata=event_metadata,
        summary_metrics=summary_metrics,
    )

    # 7. Construct Engineering Trace
    driver_codes_list = list(drivers_data.keys())
    trace = {
        "data_domain": "telemetry",
        "execution_time_ms": round((time.perf_counter() - t_start) * 1000, 2),
        "confidence": 1.0,
        "strategy_params": {
            "year": year,
            "grand_prix": gp_name,
            "session_type": event_metadata["session_type"],
            "session_key": session_key,
            "drivers": driver_codes_list,
            "driver_numbers": {d: drivers_data[d]["driver_number"] for d in driver_codes_list},
            "stint_counts": {d: len(drivers_data[d]["stints"]) for d in driver_codes_list},
            "clean_lap_counts": {d: len(drivers_data[d]["clean_laps"]) for d in driver_codes_list},
            "excluded_lap_counts": {d: len(drivers_data[d]["outliers"]) for d in driver_codes_list},
            "pit_stop_laps": {d: drivers_data[d]["pit_stops"] for d in driver_codes_list},
        },
        "notes": f"Tyre stint degradation and race strategy from OpenF1 ({session_key}) with 107% clean-lap outlier filtering and linear regression slopes.",
    }

    return {
        "metrics": summary_metrics,
        "drivers_data": drivers_data,
        "chart": {
            "chart_type": "tyre_degradation",
            "spec": chart_spec,
            "metadata": chart_spec.get("metadata", {}),
            "caption": f"Tyre Stint Degradation & Strategy: {' vs '.join(driver_codes_list)} ({year} {gp_name})",
        },
        "trace": trace,
    }
