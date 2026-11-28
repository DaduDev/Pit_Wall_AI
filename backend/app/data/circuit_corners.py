"""
Universal Circuit Corner Engine for PitWall AI.
Integrates MultiViewer circuit geometry API with local disk cache and
resolves corner nicknames before turn numbers across all 24 modern F1 circuits.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import threading
from typing import Any

import httpx

logger = logging.getLogger("pitwall.data.circuit_corners")

NICKNAMES_PATH = Path("./data/corner_nicknames.json")
LEARNED_ALIASES_PATH = Path("./data/learned_aliases.json")
CIRCUIT_CACHE_DIR = Path("./data/openf1_cache/circuits")

# Map colloquial circuit names, countries, and Grand Prix titles to OpenF1 circuit_key and slug
CIRCUIT_METADATA = {
    # Silverstone
    "silverstone": {"key": 2, "slug": "silverstone", "name": "Silverstone Circuit"},
    "british": {"key": 2, "slug": "silverstone", "name": "Silverstone Circuit"},
    "great britain": {"key": 2, "slug": "silverstone", "name": "Silverstone Circuit"},
    "uk": {"key": 2, "slug": "silverstone", "name": "Silverstone Circuit"},
    # Spa-Francorchamps
    "spa": {"key": 7, "slug": "spa", "name": "Circuit de Spa-Francorchamps"},
    "spa-francorchamps": {"key": 7, "slug": "spa", "name": "Circuit de Spa-Francorchamps"},
    "belgium": {"key": 7, "slug": "spa", "name": "Circuit de Spa-Francorchamps"},
    "belgian": {"key": 7, "slug": "spa", "name": "Circuit de Spa-Francorchamps"},
    # Monza
    "monza": {"key": 39, "slug": "monza", "name": "Autodromo Nazionale Monza"},
    "italy": {"key": 39, "slug": "monza", "name": "Autodromo Nazionale Monza"},
    "italian": {"key": 39, "slug": "monza", "name": "Autodromo Nazionale Monza"},
    # Suzuka
    "suzuka": {"key": 46, "slug": "suzuka", "name": "Suzuka International Racing Course"},
    "japan": {"key": 46, "slug": "suzuka", "name": "Suzuka International Racing Course"},
    "japanese": {"key": 46, "slug": "suzuka", "name": "Suzuka International Racing Course"},
    # Monaco
    "monaco": {"key": 22, "slug": "monaco", "name": "Circuit de Monaco"},
    "monte carlo": {"key": 22, "slug": "monaco", "name": "Circuit de Monaco"},
    # Interlagos
    "interlagos": {"key": 14, "slug": "interlagos", "name": "Autodromo Jose Carlos Pace"},
    "brazil": {"key": 14, "slug": "interlagos", "name": "Autodromo Jose Carlos Pace"},
    "brazilian": {"key": 14, "slug": "interlagos", "name": "Autodromo Jose Carlos Pace"},
    "sao paulo": {"key": 14, "slug": "interlagos", "name": "Autodromo Jose Carlos Pace"},
    "são paulo": {"key": 14, "slug": "interlagos", "name": "Autodromo Jose Carlos Pace"},
    # Zandvoort
    "zandvoort": {"key": 55, "slug": "zandvoort", "name": "Circuit Zandvoort"},
    "netherlands": {"key": 55, "slug": "zandvoort", "name": "Circuit Zandvoort"},
    "dutch": {"key": 55, "slug": "zandvoort", "name": "Circuit Zandvoort"},
    # Red Bull Ring
    "spielberg": {"key": 19, "slug": "spielberg", "name": "Red Bull Ring"},
    "red bull ring": {"key": 19, "slug": "spielberg", "name": "Red Bull Ring"},
    "austria": {"key": 19, "slug": "spielberg", "name": "Red Bull Ring"},
    "austrian": {"key": 19, "slug": "spielberg", "name": "Red Bull Ring"},
    # Hungaroring
    "hungaroring": {"key": 4, "slug": "hungaroring", "name": "Hungaroring"},
    "hungary": {"key": 4, "slug": "hungaroring", "name": "Hungaroring"},
    "hungarian": {"key": 4, "slug": "hungaroring", "name": "Hungaroring"},
    "budapest": {"key": 4, "slug": "hungaroring", "name": "Hungaroring"},
    # Montreal
    "montreal": {"key": 23, "slug": "montreal", "name": "Circuit Gilles Villeneuve"},
    "canada": {"key": 23, "slug": "montreal", "name": "Circuit Gilles Villeneuve"},
    "canadian": {"key": 23, "slug": "montreal", "name": "Circuit Gilles Villeneuve"},
    "gilles villeneuve": {"key": 23, "slug": "montreal", "name": "Circuit Gilles Villeneuve"},
    # Imola
    "imola": {"key": 6, "slug": "imola", "name": "Autodromo Enzo e Dino Ferrari"},
    "emilia romagna": {"key": 6, "slug": "imola", "name": "Autodromo Enzo e Dino Ferrari"},
    # Catalunya
    "catalunya": {"key": 15, "slug": "catalunya", "name": "Circuit de Barcelona-Catalunya"},
    "barcelona": {"key": 15, "slug": "catalunya", "name": "Circuit de Barcelona-Catalunya"},
    "spain": {"key": 15, "slug": "catalunya", "name": "Circuit de Barcelona-Catalunya"},
    "spanish": {"key": 15, "slug": "catalunya", "name": "Circuit de Barcelona-Catalunya"},
    # Melbourne
    "melbourne": {"key": 10, "slug": "melbourne", "name": "Albert Park Circuit"},
    "albert park": {"key": 10, "slug": "melbourne", "name": "Albert Park Circuit"},
    "australia": {"key": 10, "slug": "melbourne", "name": "Albert Park Circuit"},
    "australian": {"key": 10, "slug": "melbourne", "name": "Albert Park Circuit"},
    # COTA
    "austin": {"key": 9, "slug": "austin", "name": "Circuit of The Americas"},
    "cota": {"key": 9, "slug": "austin", "name": "Circuit of The Americas"},
    "americas": {"key": 9, "slug": "austin", "name": "Circuit of The Americas"},
    "united states": {"key": 9, "slug": "austin", "name": "Circuit of The Americas"},
    # Mexico City
    "mexico": {"key": 65, "slug": "mexico", "name": "Autodromo Hermanos Rodriguez"},
    "mexico city": {"key": 65, "slug": "mexico", "name": "Autodromo Hermanos Rodriguez"},
    "hermanos rodriguez": {"key": 65, "slug": "mexico", "name": "Autodromo Hermanos Rodriguez"},
    # Singapore
    "singapore": {"key": 61, "slug": "singapore", "name": "Marina Bay Street Circuit"},
    "marina bay": {"key": 61, "slug": "singapore", "name": "Marina Bay Street Circuit"},
    # Baku
    "baku": {"key": 144, "slug": "baku", "name": "Baku City Circuit"},
    "azerbaijan": {"key": 144, "slug": "baku", "name": "Baku City Circuit"},
    # Bahrain
    "sakhir": {"key": 63, "slug": "sakhir", "name": "Bahrain International Circuit"},
    "bahrain": {"key": 63, "slug": "sakhir", "name": "Bahrain International Circuit"},
    # Las Vegas
    "vegas": {"key": 152, "slug": "vegas", "name": "Las Vegas Strip Circuit"},
    "las vegas": {"key": 152, "slug": "vegas", "name": "Las Vegas Strip Circuit"},
    # Jeddah
    "jeddah": {"key": 149, "slug": "jeddah", "name": "Jeddah Corniche Circuit"},
    "saudi arabia": {"key": 149, "slug": "jeddah", "name": "Jeddah Corniche Circuit"},
    # Lusail
    "lusail": {"key": 150, "slug": "lusail", "name": "Lusail International Circuit"},
    "qatar": {"key": 150, "slug": "lusail", "name": "Lusail International Circuit"},
    # Yas Marina
    "yas_marina": {"key": 70, "slug": "yas_marina", "name": "Yas Marina Circuit"},
    "yas marina": {"key": 70, "slug": "yas_marina", "name": "Yas Marina Circuit"},
    "abu dhabi": {"key": 70, "slug": "yas_marina", "name": "Yas Marina Circuit"},
    # Miami
    "miami": {"key": 151, "slug": "miami", "name": "Miami International Autodrome"},
    # Shanghai
    "shanghai": {"key": 49, "slug": "shanghai", "name": "Shanghai International Circuit"},
    "china": {"key": 49, "slug": "shanghai", "name": "Shanghai International Circuit"},
    "chinese": {"key": 49, "slug": "shanghai", "name": "Shanghai International Circuit"},
}


class CircuitCornerEngine:
    """
    Universal Circuit Corner Engine providing:
    1. MultiViewer geometry coordinates with local disk cache.
    2. Nickname-first corner resolution to prevent '130R' from parsing as Turn 130.
    3. Dynamic alias learning saved to learned_aliases.json.
    """

    def __init__(
        self,
        nicknames_file: Path | str = NICKNAMES_PATH,
        learned_aliases_file: Path | str = LEARNED_ALIASES_PATH,
        cache_dir: Path | str = CIRCUIT_CACHE_DIR,
    ):
        self.nicknames_file = Path(nicknames_file)
        self.learned_aliases_file = Path(learned_aliases_file)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._nicknames: list[dict[str, Any]] = []
        self._learned_aliases: dict[str, Any] = {}
        self._load_nickname_sources()

    def _load_nickname_sources(self) -> None:
        """Load curated and learned corner nicknames from disk."""
        if self.nicknames_file.exists():
            try:
                with open(self.nicknames_file, "r", encoding="utf-8") as f:
                    self._nicknames = json.load(f)
            except Exception as e:
                logger.error(f"Error loading {self.nicknames_file}: {e}")
                self._nicknames = []

        if self.learned_aliases_file.exists():
            try:
                with open(self.learned_aliases_file, "r", encoding="utf-8") as f:
                    self._learned_aliases = json.load(f)
            except Exception as e:
                logger.error(f"Error loading {self.learned_aliases_file}: {e}")
                self._learned_aliases = {}
        else:
            self._learned_aliases = {}

    def get_circuit_info(self, circuit_identifier: str | int) -> dict[str, Any] | None:
        """Resolve a circuit identifier (name, GP, key, slug) to canonical metadata."""
        if isinstance(circuit_identifier, int):
            for info in CIRCUIT_METADATA.values():
                if info["key"] == circuit_identifier:
                    return info
            return {"key": circuit_identifier, "slug": f"circuit_{circuit_identifier}", "name": f"Circuit {circuit_identifier}"}

        norm = str(circuit_identifier).lower().strip()
        # Direct lookup
        if norm in CIRCUIT_METADATA:
            return CIRCUIT_METADATA[norm]

        # Partial matching
        for k, info in CIRCUIT_METADATA.items():
            if k in norm or norm in k:
                return info

        return None

    def fetch_circuit_geometry(self, circuit_key: int, year: int = 2024) -> dict[str, Any] | None:
        """
        Fetch MultiViewer circuit geometry from disk cache or upstream API.
        """
        cache_file = self.cache_dir / f"{circuit_key}_{year}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading circuit cache {cache_file}: {e}")

        url = f"https://api.multiviewer.app/api/v1/circuits/{circuit_key}/{year}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers={"User-Agent": "PitWallAI/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    try:
                        with self._lock:
                            self.cache_dir.mkdir(parents=True, exist_ok=True)
                            with open(cache_file, "w", encoding="utf-8") as f:
                                json.dump(data, f)
                    except Exception as ce:
                        logger.warning(f"Could not persist circuit geometry cache {cache_file}: {ce}")
                    return data
                logger.warning(f"MultiViewer API returned {resp.status_code} for circuit {circuit_key}/{year}")
        except Exception as e:
            logger.warning(f"Failed to fetch MultiViewer geometry for {circuit_key}/{year}: {e}")

        # Check fallback to previous year if current year not available
        if year != 2024:
            return self.fetch_circuit_geometry(circuit_key, year=2024)

        return None

    def get_corner_coordinates(self, circuit_key: int, turn_number: int, year: int = 2024) -> dict[str, Any] | None:
        """Get precise track coordinates (x, y) for a turn from MultiViewer geometry."""
        geom = self.fetch_circuit_geometry(circuit_key, year)
        if not geom or "corners" not in geom:
            return None

        for corner in geom.get("corners", []):
            if corner.get("number") == turn_number:
                pos = corner.get("trackPosition") or {}
                return {
                    "x": pos.get("x"),
                    "y": pos.get("y"),
                    "angle": corner.get("angle"),
                    "length": corner.get("length"),
                }
        return None

    def resolve_corner(
        self,
        circuit_query: str | int,
        corner_query: str,
        year: int = 2024,
    ) -> dict[str, Any]:
        """
        Resolve a corner query for a given circuit.
        GUARANTEE: Checks nicknames and learned aliases BEFORE numeric regexes
        so '130R' NEVER resolves to Turn 130!
        """
        circuit_info = self.get_circuit_info(circuit_query)
        circuit_slug = circuit_info["slug"] if circuit_info else str(circuit_query).lower()
        circuit_key = circuit_info["key"] if circuit_info else 0
        circuit_name = circuit_info["name"] if circuit_info else str(circuit_query)

        query_clean = corner_query.strip().lower()

        # Step 1: Check Learned Aliases first (web verified)
        alias_key = f"{circuit_slug}:{query_clean}"
        if alias_key in self._learned_aliases:
            learned = self._learned_aliases[alias_key]
            turn_number = learned["turn_number"]
            nickname = learned.get("nickname", corner_query)
            coords = self.get_corner_coordinates(circuit_key, turn_number, year)
            return {
                "resolved": True,
                "circuit_key": circuit_key,
                "circuit_slug": circuit_slug,
                "circuit_name": circuit_name,
                "turn_number": turn_number,
                "nickname": nickname,
                "coordinates": coords,
                "distance_m": learned.get("distance_m", 0.0),
                "source": "learned_aliases",
            }

        # Step 2: Check Curated Nicknames (BEFORE any digit/turn regex)
        # First exact or word-boundary match
        matched_entry = None
        for entry in self._nicknames:
            if entry["circuit_key"] == circuit_slug:
                entry_nick = entry["nickname"].strip().lower()
                # Exact match or normalized match (e.g., '130r' == '130r', 'copse' in 'copse corner')
                if query_clean == entry_nick:
                    matched_entry = entry
                    break
                # Handle punctuation and partial phrasing: 'turn 130r' or 'copse corner'
                cleaned_entry_nick = re.sub(r"[^a-z0-9]", "", entry_nick)
                cleaned_query = re.sub(r"[^a-z0-9]", "", query_clean)
                if cleaned_entry_nick and cleaned_entry_nick == cleaned_query:
                    matched_entry = entry
                    break
                if entry_nick in query_clean and len(entry_nick) >= 4:
                    matched_entry = entry
                    break

        if matched_entry:
            turn_number = matched_entry["turn_number"]
            nickname = matched_entry["nickname"]
            distance_m = matched_entry.get("distance_m", 0.0)
            coords = self.get_corner_coordinates(circuit_key, turn_number, year)
            return {
                "resolved": True,
                "circuit_key": circuit_key,
                "circuit_slug": circuit_slug,
                "circuit_name": circuit_name,
                "turn_number": turn_number,
                "nickname": nickname,
                "coordinates": coords,
                "distance_m": distance_m,
                "source": "curated_nicknames",
            }

        # Step 3: Only if no nickname matched, check for explicit Turn numbers
        turn_match = re.search(r"(?:turn|corner|curva|t)\s*(\d+)", query_clean)
        if not turn_match:
            # Standalone number: "1", "4", "15" (do NOT match "130r" because of the trailing 'r')
            turn_match = re.search(r"^\s*(\d+)\s*$", query_clean)

        if turn_match:
            turn_number = int(turn_match.group(1))
            coords = self.get_corner_coordinates(circuit_key, turn_number, year)
            return {
                "resolved": True,
                "circuit_key": circuit_key,
                "circuit_slug": circuit_slug,
                "circuit_name": circuit_name,
                "turn_number": turn_number,
                "nickname": f"Turn {turn_number}",
                "coordinates": coords,
                "distance_m": 0.0,
                "source": "numeric_turn",
            }

        # Step 4: Corner is unknown
        return {
            "resolved": False,
            "unknown_corner": True,
            "query": corner_query,
            "circuit": circuit_name,
            "circuit_slug": circuit_slug,
            "circuit_key": circuit_key,
            "hint": f"Unknown corner '{corner_query}' at {circuit_name}. Please specify a valid corner nickname or Turn number.",
        }

    def learn_alias(
        self,
        circuit_slug: str,
        nickname: str,
        turn_number: int,
        distance_m: float = 0.0,
        source: str = "web_verified",
    ) -> None:
        """Persist a new discovered corner alias to learned_aliases.json."""
        alias_key = f"{circuit_slug.lower()}:{nickname.strip().lower()}"
        with self._lock:
            self._learned_aliases[alias_key] = {
                "circuit_slug": circuit_slug.lower(),
                "nickname": nickname.strip(),
                "turn_number": turn_number,
                "distance_m": distance_m,
                "source": source,
            }
            try:
                with open(self.learned_aliases_file, "w", encoding="utf-8") as f:
                    json.dump(self._learned_aliases, f, indent=2)
                logger.info(f"Learned alias saved: {alias_key} -> Turn {turn_number}")
            except Exception as e:
                logger.error(f"Failed to persist learned alias {alias_key}: {e}")


# Singleton instance
_engine_instance: CircuitCornerEngine | None = None
_engine_lock = threading.Lock()


def get_circuit_corner_engine() -> CircuitCornerEngine:
    """Get or initialize singleton CircuitCornerEngine."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            _engine_instance = CircuitCornerEngine()
        return _engine_instance
