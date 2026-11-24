"""
Entity Resolver for PitWall AI.
Provides fuzzy and canonical matching for:
- Driver identities (code, surname, forename, full name)
- Circuit references (name, country, circuitRef)
- Corner nicknames and turn numbers (from corner_nicknames.json)
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from rapidfuzz import process, fuzz
from backend.app.config import settings

# In-memory cache for corner nicknames
_CORNER_NICKNAMES_CACHE: Optional[List[Dict[str, Any]]] = None

def load_corner_nicknames() -> List[Dict[str, Any]]:
    """Loads corner nicknames mapping from JSON file."""
    global _CORNER_NICKNAMES_CACHE
    if _CORNER_NICKNAMES_CACHE is not None:
        return _CORNER_NICKNAMES_CACHE

    target_path = settings.CORNER_NICKNAMES_PATH
    if not target_path.exists():
        # Fallback to backend/data/corner_nicknames.json
        alt_path = settings.ROOT_DIR / "backend" / "data" / "corner_nicknames.json"
        if alt_path.exists():
            target_path = alt_path

    if target_path.exists():
        with open(target_path, "r", encoding="utf-8") as f:
            _CORNER_NICKNAMES_CACHE = json.load(f)
    else:
        _CORNER_NICKNAMES_CACHE = []

    return _CORNER_NICKNAMES_CACHE


def resolve_corner(circuit_key: str, corner_query: Union[str, int]) -> Optional[Dict[str, Any]]:
    """
    Resolves a corner for a specific circuit by nickname or turn number.
    Returns: {"circuit_key": str, "turn_number": int, "nickname": str, "distance_m": float}
    """
    corners = load_corner_nicknames()
    normalized_circuit = circuit_key.strip().lower()

    # Filter corners belonging to this circuit
    circuit_corners = [
        c for c in corners if c["circuit_key"].lower() in normalized_circuit or normalized_circuit in c["circuit_key"].lower()
    ]

    # Case 1: Corner query is an integer or numeric string (e.g. 9 or "Turn 9")
    query_str = str(corner_query).strip()
    digits = "".join(ch for ch in query_str if ch.isdigit())
    if digits:
        turn_num = int(digits)
        for c in circuit_corners:
            if c["turn_number"] == turn_num:
                return c
        # If not in curated list with nickname, synthesize basic corner info
        return {
            "circuit_key": circuit_key,
            "turn_number": turn_num,
            "nickname": f"Turn {turn_num}",
            "distance_m": None,
        }

    # Case 2: Corner query is a nickname (e.g. "Copse", "Eau Rouge")
    if not circuit_corners:
        # Check all corners regardless of circuit if circuit didn't match directly
        circuit_corners = corners

    nicknames = [c["nickname"] for c in circuit_corners]
    if not nicknames:
        return None

    match, score, idx = process.extractOne(query_str, nicknames, scorer=fuzz.token_sort_ratio)
    if score >= 65:
        return circuit_corners[idx]

    return None


GP_CIRCUIT_ALIASES: Dict[str, str] = {
    "brazil": "interlagos",
    "brazilian": "interlagos",
    "brazilian grand prix": "interlagos",
    "sao paulo": "interlagos",
    "são paulo": "interlagos",
    "interlagos": "interlagos",
    "suzuka": "suzuka",
    "japan": "suzuka",
    "japanese": "suzuka",
    "japanese grand prix": "suzuka",
    "monza": "monza",
    "italy": "monza",
    "italian": "monza",
    "italian grand prix": "monza",
    "imola": "imola",
    "emilia romagna": "imola",
    "san marino": "imola",
    "spa": "spa",
    "belgium": "spa",
    "belgian": "spa",
    "belgian grand prix": "spa",
    "silverstone": "silverstone",
    "britain": "silverstone",
    "british": "silverstone",
    "british grand prix": "silverstone",
    "monaco": "monaco",
    "monte carlo": "monaco",
    "zandvoort": "zandvoort",
    "dutch": "zandvoort",
    "netherlands": "zandvoort",
    "austria": "red_bull_ring",
    "austrian": "red_bull_ring",
    "spielberg": "red_bull_ring",
    "red bull ring": "red_bull_ring",
    "mexico": "rodriguez",
    "mexican": "rodriguez",
    "mexico city": "rodriguez",
    "cota": "americas",
    "austin": "americas",
    "united states": "americas",
    "canada": "villeneuve",
    "canadian": "villeneuve",
    "montreal": "villeneuve",
    "bahrain": "bahrain",
    "sakhir": "bahrain",
    "jeddah": "jeddah",
    "saudi": "jeddah",
    "saudi arabia": "jeddah",
    "abu dhabi": "yas_marina",
    "yas marina": "yas_marina",
    "qatar": "losail",
    "lusail": "losail",
    "losail": "losail",
    "singapore": "marina_bay",
    "marina bay": "marina_bay",
    "baku": "baku",
    "azerbaijan": "baku",
    "melbourne": "albert_park",
    "australia": "albert_park",
    "australian": "albert_park",
    "shanghai": "shanghai",
    "china": "shanghai",
    "chinese": "shanghai",
    "barcelona": "catalunya",
    "catalunya": "catalunya",
    "spain": "catalunya",
    "hungary": "hungaroring",
    "hungaroring": "hungaroring",
    "las vegas": "vegas",
    "miami": "miami",
}


class EntityResolver:
    """
    Fuzzy resolver for Driver and Circuit entities using DuckDB historical records.
    """

    def __init__(self, duckdb_manager=None):
        from backend.app.data.duckdb_manager import get_duckdb_manager
        self.duckdb = duckdb_manager or get_duckdb_manager()
        self._drivers_cache: Optional[List[Dict[str, Any]]] = None
        self._circuits_cache: Optional[List[Dict[str, Any]]] = None

    def _ensure_drivers_loaded(self) -> List[Dict[str, Any]]:
        if self._drivers_cache is None:
            conn = self.duckdb.get_connection()
            # Order by driverId DESC so modern drivers take precedence over older drivers with same code
            rows = conn.execute("""
                SELECT driverId, driverRef, number, code, forename, surname, nationality
                FROM drivers
                ORDER BY driverId DESC
            """).fetchall()
            cols = ["driverId", "driverRef", "number", "code", "forename", "surname", "nationality"]
            self._drivers_cache = []
            for r in rows:
                d = dict(zip(cols, r))
                d["full_name"] = f"{d['forename']} {d['surname']}"
                self._drivers_cache.append(d)
        return self._drivers_cache

    def _ensure_circuits_loaded(self) -> List[Dict[str, Any]]:
        if self._circuits_cache is None:
            conn = self.duckdb.get_connection()
            rows = conn.execute("""
                SELECT circuitId, circuitRef, name, location, country
                FROM circuits
            """).fetchall()
            cols = ["circuitId", "circuitRef", "name", "location", "country"]
            self._circuits_cache = [dict(zip(cols, r)) for r in rows]
        return self._circuits_cache

    def resolve_driver(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Resolves driver by code (VER), surname (Verstappen), full name, or forename.
        """
        drivers = self._ensure_drivers_loaded()
        q = query.strip().lower()

        # 1. Exact match on 3-letter code
        if len(q) == 3:
            for d in drivers:
                if d.get("code") and d["code"].lower() == q:
                    return d

        # 2. Exact match on surname or full name
        for d in drivers:
            if d["surname"].lower() == q or d["full_name"].lower() == q or d["driverRef"].lower() == q:
                return d

        # 3. Exact match on forename if unambiguous or well-known
        for d in drivers:
            if d["forename"].lower() == q:
                return d

        # 4. Fuzzy match on full names and surnames
        choices = {f"{d['full_name']} ({d.get('code') or ''})": d for d in drivers}
        names_list = list(choices.keys())
        match, score, _ = process.extractOne(query, names_list, scorer=fuzz.WRatio)
        if score >= 70:
            return choices[match]

        return None

    def resolve_circuit(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Resolves circuit by name, circuitRef, location, country, or canonical Grand Prix alias.
        """
        circuits = self._ensure_circuits_loaded()
        q = query.strip().lower()

        # 0. Canonical GP / Circuit Aliases (e.g. "Brazil", "Interlagos", "Suzuka")
        alias_target = GP_CIRCUIT_ALIASES.get(q)
        if not alias_target:
            # Check if any alias key is contained in query (longest phrases first)
            for alias_key, target in sorted(GP_CIRCUIT_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
                if re.search(rf"\b{re.escape(alias_key)}\b", q) or alias_key in q:
                    alias_target = target
                    break

        if alias_target:
            for c in circuits:
                if c["circuitRef"].lower() == alias_target:
                    return c

        # 1. Exact match on circuitRef or name
        for c in circuits:
            if c["circuitRef"].lower() == q or c["name"].lower() == q:
                return c

        # 2. Substring match on location or country
        for c in circuits:
            if q in c["location"].lower() or q in c["country"].lower():
                return c

        # 3. Fuzzy match across all circuits
        choices = {f"{c['name']} {c['location']} {c['country']}": c for c in circuits}
        names_list = list(choices.keys())
        match, score, _ = process.extractOne(query, names_list, scorer=fuzz.token_set_ratio)
        if score >= 65:
            return choices[match]

        return None
