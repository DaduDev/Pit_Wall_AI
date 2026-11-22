"""
OpenF1 REST API Client & Persistent Disk Cache for PitWall AI.
Replaces paywalled FastF1 live timing with OpenF1 (https://api.openf1.org/v1/)
for free, unauthenticated telemetry from 2023 onward.

Features:
- Persistent disk caching in ./data/openf1_cache/ (instant repeat queries)
- Lightweight rate limiter (<= 2.5 req/sec, max 28 req/min, 429 exponential backoff)
- Free unauthenticated access to sessions, drivers, laps, car_data, location, stints, position, pit
- Timestamp alignment via pd.merge_asof (UTC)
- Cumulative Distance integration (Speed * dt) scaled to circuit lap length
- Native team colors from OpenF1 drivers.team_colour
"""

from collections import deque
import hashlib
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import httpx
import numpy as np
import pandas as pd

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Standard circuit lap lengths in meters for normalization
CIRCUIT_LENGTHS_M = {
    "silverstone": 5891.0,
    "spa": 7004.0,
    "spa-francorchamps": 7004.0,
    "monza": 5793.0,
    "monaco": 3337.0,
    "monte carlo": 3337.0,
    "suzuka": 5807.0,
    "zandvoort": 4259.0,
    "red_bull_ring": 4318.0,
    "spielberg": 4318.0,
    "catalunya": 4657.0,
    "barcelona": 4657.0,
    "hungaroring": 4381.0,
    "marina_bay": 4940.0,
    "singapore": 4940.0,
    "cota": 5513.0,
    "austin": 5513.0,
    "interlagos": 4309.0,
    "sao paulo": 4309.0,
    "são paulo": 4309.0,
    "yas_marina": 5281.0,
    "abu_dhabi": 5281.0,
    "bahrain": 5412.0,
    "sakhir": 5412.0,
    "jeddah": 6174.0,
    "melbourne": 5278.0,
    "albert_park": 5278.0,
    "baku": 6003.0,
    "miami": 5412.0,
    "montreal": 4361.0,
    "villeneuve": 4361.0,
    "las_vegas": 6201.0,
    "losail": 5419.0,
    "lusail": 5419.0,
    "qatar": 5419.0,
    "imola": 4909.0,
    "shanghai": 5451.0,
    "mexico_city": 4304.0,
}

# Grand Prix / Circuit aliases for flexible entity resolution
CIRCUIT_ALIASES = {
    "british": "silverstone",
    "britain": "silverstone",
    "silverstone": "silverstone",
    "belgian": "spa-francorchamps",
    "belgium": "spa-francorchamps",
    "spa": "spa-francorchamps",
    "spa-francorchamps": "spa-francorchamps",
    "italian": "monza",
    "italy": "monza",
    "monza": "monza",
    "japanese": "suzuka",
    "japan": "suzuka",
    "suzuka": "suzuka",
    "dutch": "zandvoort",
    "netherlands": "zandvoort",
    "zandvoort": "zandvoort",
    "monaco": "monte carlo",
    "monte carlo": "monte carlo",
    "brazilian": "interlagos",
    "brazil": "interlagos",
    "interlagos": "interlagos",
    "sao paulo": "interlagos",
    "austrian": "spielberg",
    "austria": "spielberg",
    "spielberg": "spielberg",
    "red bull ring": "spielberg",
    "bahrain": "sakhir",
    "sakhir": "sakhir",
    "saudi": "jeddah",
    "saudi arabia": "jeddah",
    "jeddah": "jeddah",
    "australian": "melbourne",
    "australia": "melbourne",
    "melbourne": "melbourne",
    "azerbaijan": "baku",
    "baku": "baku",
    "miami": "miami",
    "emilia": "imola",
    "imola": "imola",
    "monaco": "monte carlo",
    "canadian": "montreal",
    "canada": "montreal",
    "montreal": "montreal",
    "spanish": "catalunya",
    "spain": "catalunya",
    "catalunya": "catalunya",
    "barcelona": "catalunya",
    "hungarian": "hungaroring",
    "hungary": "hungaroring",
    "hungaroring": "hungaroring",
    "singapore": "singapore",
    "united states": "austin",
    "cota": "austin",
    "austin": "austin",
    "mexico": "mexico city",
    "mexican": "mexico city",
    "las vegas": "las vegas",
    "qatar": "lusail",
    "lusail": "lusail",
    "abu dhabi": "yas marina circuit",
    "chinese": "shanghai",
    "china": "shanghai",
    "shanghai": "shanghai",
}

# Session type mapping
SESSION_TYPE_MAP = {
    "q": "Qualifying",
    "qualifying": "Qualifying",
    "r": "Race",
    "race": "Race",
    "fp1": "Practice 1",
    "practice 1": "Practice 1",
    "fp2": "Practice 2",
    "practice 2": "Practice 2",
    "fp3": "Practice 3",
    "practice 3": "Practice 3",
    "sq": "Sprint Qualifying",
    "sprint qualifying": "Sprint Qualifying",
    "sprint shootout": "Sprint Qualifying",
    "sprint": "Sprint",
}


class OpenF1Client:
    """
    HTTP client for the free OpenF1 REST API with disk caching and rate limiting.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        base_url: Optional[str] = None,
        min_request_interval: float = 0.42,  # ~2.38 req/s
        max_requests_per_minute: int = 28,   # Safe margin under OpenF1 30 req/min cap
    ):
        self.cache_dir = cache_dir or settings.OPENF1_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = (base_url or settings.OPENF1_BASE_URL).rstrip("/")
        self.min_interval = min_request_interval
        self.max_per_minute = max_requests_per_minute

        self._lock = threading.Lock()
        self._last_request_time = 0.0
        self._request_timestamps: deque = deque()

    def _get_cache_path(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Path:
        """Generates deterministic safe filename for local JSON cache."""
        param_str = ""
        if params:
            sorted_items = sorted((str(k), str(v)) for k, v in params.items())
            param_str = "_".join(f"{k}={v}" for k, v in sorted_items)

        # If simple and short, use readable name; otherwise hash
        safe_param_slug = re.sub(r'[^a-zA-Z0-9_\-=]', '_', param_str)
        if len(safe_param_slug) <= 80 and not any(c in param_str for c in "><:?*|\""):
            filename = f"{endpoint}_{safe_param_slug}.json" if safe_param_slug else f"{endpoint}.json"
        else:
            h = hashlib.md5(param_str.encode("utf-8")).hexdigest()[:12]
            filename = f"{endpoint}_{h}.json"

        return self.cache_dir / filename

    def _wait_for_rate_limit(self):
        """Enforces <= 2.5 req/sec and <= 28 req/min rate limits."""
        with self._lock:
            now = time.time()

            # 1. Purge timestamps older than 60 seconds
            while self._request_timestamps and now - self._request_timestamps[0] > 60.0:
                self._request_timestamps.popleft()

            # 2. Per-minute limit check
            if len(self._request_timestamps) >= self.max_per_minute:
                oldest = self._request_timestamps[0]
                sleep_sec = max(0.0, 60.0 - (now - oldest) + 0.1)
                logger.info(f"OpenF1 rate limit guard: reached {len(self._request_timestamps)} req/min. Sleeping {sleep_sec:.2f}s...")
                time.sleep(sleep_sec)
                now = time.time()

            # 3. Per-second interval check
            elapsed_since_last = now - self._last_request_time
            if elapsed_since_last < self.min_interval:
                time.sleep(self.min_interval - elapsed_since_last)

            now = time.time()
            self._last_request_time = now
            self._request_timestamps.append(now)

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        max_retries: int = 3,
    ) -> Any:
        """
        Executes GET request against OpenF1 API with cache-first lookup and 429 backoff retry.
        """
        cache_path = self._get_cache_path(endpoint, params)

        # 1. Cache hit
        if use_cache and cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except Exception as e:
                logger.warning(f"Failed to read cache file {cache_path}: {e}")

        # 2. Network fetch with rate-limiter and retry
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}

        last_err = None
        for attempt in range(max_retries + 1):
            self._wait_for_rate_limit()
            try:
                with httpx.Client(timeout=20.0) as client:
                    resp = client.get(url, params=clean_params)

                if resp.status_code == 200:
                    data = resp.json()
                    # Cache successful response
                    try:
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(data, f)
                    except Exception as ce:
                        logger.warning(f"Could not write cache file {cache_path}: {ce}")
                    return data

                elif resp.status_code == 429:
                    retry_after = 2.0 * (2 ** attempt)
                    if "Retry-After" in resp.headers:
                        try:
                            retry_after = float(resp.headers["Retry-After"])
                        except ValueError:
                            pass
                    logger.warning(f"OpenF1 429 rate limit hit. Backing off for {retry_after}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_after)
                    continue

                elif resp.status_code == 404:
                    # Session or lap not found
                    return []

                else:
                    resp.raise_for_status()

            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    wait_sec = 1.0 * (2 ** attempt)
                    logger.warning(f"OpenF1 request error: {e}. Retrying in {wait_sec}s...")
                    time.sleep(wait_sec)
                else:
                    logger.error(f"OpenF1 request failed after {max_retries + 1} attempts for {url}: {e}")

        raise RuntimeError(f"OpenF1 request failed for {endpoint}: {last_err}") from last_err

    # -------------------------------------------------------------
    # Core Endpoint Wrappers
    # -------------------------------------------------------------

    def get_sessions(
        self,
        year: Optional[int] = None,
        circuit_short_name: Optional[str] = None,
        country_name: Optional[str] = None,
        session_name: Optional[str] = None,
        session_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches F1 sessions from OpenF1."""
        params: Dict[str, Any] = {}
        if year is not None:
            params["year"] = year
        if circuit_short_name is not None:
            params["circuit_short_name"] = circuit_short_name
        if country_name is not None:
            params["country_name"] = country_name
        if session_name is not None:
            params["session_name"] = session_name
        if session_type is not None:
            params["session_type"] = session_type

        data = self.get("sessions", params)
        return data if isinstance(data, list) else []

    def get_drivers(self, session_key: int) -> List[Dict[str, Any]]:
        """Fetches driver details for a given session."""
        data = self.get("drivers", {"session_key": session_key})
        return data if isinstance(data, list) else []

    def get_laps(
        self,
        session_key: int,
        driver_number: Optional[int] = None,
        lap_number: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches lap timings for a session / driver."""
        params: Dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        if lap_number is not None:
            params["lap_number"] = lap_number
        data = self.get("laps", params)
        return data if isinstance(data, list) else []

    def get_car_data(
        self,
        session_key: int,
        driver_number: int,
        date_start: str,
        date_end: str,
    ) -> List[Dict[str, Any]]:
        """Fetches high-frequency telemetry channels (Speed, Throttle, Brake, Gear, RPM, DRS)."""
        params = {
            "session_key": session_key,
            "driver_number": driver_number,
            "date>": date_start,
            "date<": date_end,
        }
        data = self.get("car_data", params)
        return data if isinstance(data, list) else []

    def get_location(
        self,
        session_key: int,
        driver_number: int,
        date_start: str,
        date_end: str,
    ) -> List[Dict[str, Any]]:
        """Fetches high-frequency GPS coordinates (X, Y, Z)."""
        params = {
            "session_key": session_key,
            "driver_number": driver_number,
            "date>": date_start,
            "date<": date_end,
        }
        data = self.get("location", params)
        return data if isinstance(data, list) else []

    def get_stints(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetches stint details and tyre compound data."""
        params: Dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        data = self.get("stints", params)
        return data if isinstance(data, list) else []

    def get_position(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetches driver running positions during session."""
        params: Dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        data = self.get("position", params)
        return data if isinstance(data, list) else []

    def get_pit(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetches pit stop details."""
        params: Dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        data = self.get("pit", params)
        return data if isinstance(data, list) else []

    # -------------------------------------------------------------
    # High-Level Telemetry Resolution & Processing
    # -------------------------------------------------------------

    def resolve_session(
        self,
        year: int,
        grand_prix: str,
        session_type: str = "Q",
    ) -> Optional[Dict[str, Any]]:
        """
        Resolves a session record from year, circuit/grand prix name, and session type.
        """
        all_sessions = self.get_sessions(year=year)
        if not all_sessions:
            return None

        # Normalize target session type
        target_session = SESSION_TYPE_MAP.get(session_type.lower().strip(), "Qualifying")

        # Normalize target circuit
        clean_gp = grand_prix.lower().strip()
        matched_circuit_key = None
        for alias, target in CIRCUIT_ALIASES.items():
            if alias in clean_gp:
                matched_circuit_key = target
                break
        if not matched_circuit_key:
            matched_circuit_key = clean_gp

        # Filter candidate sessions
        candidates = []
        for s in all_sessions:
            circ = (s.get("circuit_short_name") or "").lower()
            country = (s.get("country_name") or "").lower()
            loc = (s.get("location") or "").lower()

            if (
                matched_circuit_key in circ
                or circ in matched_circuit_key
                or matched_circuit_key in country
                or matched_circuit_key in loc
            ):
                candidates.append(s)

        if not candidates:
            # Fallback: substring match on raw grand_prix string
            for s in all_sessions:
                circ = (s.get("circuit_short_name") or "").lower()
                if any(word in circ for word in clean_gp.split() if len(word) > 3):
                    candidates.append(s)

        # Match session type within candidates
        for s in candidates:
            s_name = s.get("session_name", "")
            s_type = s.get("session_type", "")
            if (
                target_session.lower() in s_name.lower()
                or target_session.lower() in s_type.lower()
                or s_type.lower() == target_session.lower()
            ):
                return s

        return candidates[0] if candidates else None

    def load_openf1_driver_lap(
        self,
        year: int,
        grand_prix: str,
        driver_code: str,
        session_type: str = "Q",
        lap_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Loads aligned car channels and GPS coordinates for a driver's lap via OpenF1.
        1. Resolves session
        2. Resolves driver and driver_number
        3. Fetches laps and identifies target (or fastest) lap
        4. Fetches car_data and location across lap interval
        5. Aligns channels via pd.merge_asof (UTC date)
        6. Computes elapsed Time and integrated Distance
        7. Scales Distance to circuit lap length
        """
        # 1. Resolve session
        session = self.resolve_session(year=year, grand_prix=grand_prix, session_type=session_type)
        if not session:
            raise ValueError(f"Could not find OpenF1 session for {year} {grand_prix} '{session_type}'")

        session_key = session["session_key"]
        circuit_name = session.get("circuit_short_name", grand_prix)

        # 2. Resolve driver
        drivers = self.get_drivers(session_key=session_key)
        drv = None
        code_upper = driver_code.strip().upper()

        for d in drivers:
            acronym = (d.get("name_acronym") or "").upper()
            last_name = (d.get("last_name") or "").upper()
            full_name = (d.get("full_name") or "").upper()
            num_str = str(d.get("driver_number", ""))

            if code_upper in (acronym, num_str) or code_upper in last_name or code_upper in full_name:
                drv = d
                break

        if not drv:
            raise ValueError(f"Driver '{driver_code}' not found in OpenF1 session {session_key} ({year} {circuit_name})")

        driver_number = drv["driver_number"]
        team_name = drv.get("team_name", "Unknown")
        team_colour = drv.get("team_colour") or "38BDF8"
        team_color = f"#{team_colour.lstrip('#')}"

        # 3. Fetch laps
        laps = self.get_laps(session_key=session_key, driver_number=driver_number)
        if not laps:
            raise ValueError(f"No laps recorded for {driver_code} in OpenF1 session {session_key}")

        valid_laps = [l for l in laps if l.get("lap_duration") is not None and l.get("date_start") is not None]
        if not valid_laps:
            raise ValueError(f"No valid timed laps for {driver_code} in OpenF1 session {session_key}")

        if lap_number is not None:
            matched_laps = [l for l in valid_laps if l.get("lap_number") == lap_number]
            target_lap = matched_laps[0] if matched_laps else min(valid_laps, key=lambda l: l["lap_duration"])
        else:
            target_lap = min(valid_laps, key=lambda l: l["lap_duration"])

        actual_lap_number = target_lap["lap_number"]
        lap_duration = float(target_lap["lap_duration"])
        t_start_str = target_lap["date_start"]

        # Parse start and end date (+0.5s safety buffer for exit telemetry)
        dt_start = datetime.fromisoformat(t_start_str)
        dt_end = dt_start + timedelta(seconds=lap_duration + 0.5)
        t_end_str = dt_end.isoformat()

        # 4. Fetch car_data & location
        car_raw = self.get_car_data(session_key, driver_number, t_start_str, t_end_str)
        loc_raw = self.get_location(session_key, driver_number, t_start_str, t_end_str)

        if not car_raw:
            raise ValueError(f"No car telemetry data available for {driver_code} on Lap {actual_lap_number}")

        # 5. Build DataFrames & Align by UTC timestamp
        car_df = pd.DataFrame(car_raw)
        car_df["date"] = pd.to_datetime(car_df["date"])
        car_df = car_df.sort_values("date").reset_index(drop=True)

        if loc_raw:
            loc_df = pd.DataFrame(loc_raw)
            loc_df["date"] = pd.to_datetime(loc_df["date"])
            loc_df = loc_df.sort_values("date").reset_index(drop=True)
            merged = pd.merge_asof(
                car_df,
                loc_df[["date", "x", "y", "z"]],
                on="date",
                direction="nearest",
            )
            merged["X"] = merged["x"].fillna(0.0).astype(float)
            merged["Y"] = merged["y"].fillna(0.0).astype(float)
            merged["Z"] = merged["z"].fillna(0.0).astype(float)
        else:
            merged = car_df.copy()
            merged["X"] = 0.0
            merged["Y"] = 0.0
            merged["Z"] = 0.0

        # Channel normalization
        merged["Speed"] = merged["speed"].astype(float)
        merged["Throttle"] = merged["throttle"].astype(float)
        merged["Brake"] = np.where(merged["brake"] > 0, 100.0, 0.0)
        merged["nGear"] = merged["n_gear"].astype(int)
        merged["RPM"] = merged["rpm"].astype(float) if "rpm" in merged else 0.0
        merged["DRS"] = merged["drs"].astype(int) if "drs" in merged else 0

        # Elapsed time in seconds
        t0 = merged["date"].iloc[0]
        merged["Time"] = (merged["date"] - t0).dt.total_seconds().to_numpy(dtype=float)

        # 6. Cumulative Distance (Speed in km/h -> m/s integrated over dt)
        speeds_ms = merged["Speed"].to_numpy() * (1000.0 / 3600.0)
        dt = np.diff(merged["Time"].to_numpy(), prepend=0.0)
        dt[0] = 0.0
        merged["Distance"] = np.cumsum(speeds_ms * dt)

        # 7. Scale Distance to standard circuit lap length if available
        circ_key_clean = re.sub(r'[^a-zA-Z0-9]', '', circuit_name.lower())
        target_len = None
        for ck, cl in CIRCUIT_LENGTHS_M.items():
            if re.sub(r'[^a-zA-Z0-9]', '', ck) in circ_key_clean or circ_key_clean in re.sub(r'[^a-zA-Z0-9]', '', ck):
                target_len = cl
                break

        max_dist = merged["Distance"].iloc[-1]
        if target_len and max_dist > 0:
            scale = target_len / max_dist
            merged["Distance"] = merged["Distance"] * scale

        # Tyre compound from stints
        compound = "SOFT"
        stints = self.get_stints(session_key=session_key, driver_number=driver_number)
        for s in stints:
            lap_s = s.get("lap_start", 0) or 0
            lap_e = s.get("lap_end", 999) or 999
            if lap_s <= actual_lap_number <= lap_e:
                compound = str(s.get("compound", "SOFT")).upper()
                break

        metadata = {
            "event_name": session.get("circuit_short_name", grand_prix),
            "year": year,
            "session_type": session.get("session_name", session_type),
            "driver_code": (drv.get("name_acronym") or driver_code).upper(),
            "driver_number": driver_number,
            "lap_number": actual_lap_number,
            "lap_time": lap_duration,
            "compound": compound,
            "team": team_name,
            "team_color": team_color,
            "weather": "Dry",
        }

        # Keep clean sorted columns
        cols = ["Distance", "Speed", "Throttle", "Brake", "nGear", "RPM", "DRS", "X", "Y", "Z", "Time"]
        clean_df = merged[cols].drop_duplicates(subset=["Distance"]).sort_values("Distance").reset_index(drop=True)

        return {"telemetry": clean_df, "metadata": metadata}


# Global singleton instance
_openf1_client: Optional[OpenF1Client] = None


def get_openf1_client() -> OpenF1Client:
    """Returns application-wide singleton OpenF1Client."""
    global _openf1_client
    if _openf1_client is None:
        _openf1_client = OpenF1Client()
    return _openf1_client
