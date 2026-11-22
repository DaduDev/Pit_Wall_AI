"""
Unit tests for Driver, Circuit, and Corner Nickname Entity Resolution.
"""

import pytest
from backend.app.data.duckdb_manager import DuckDBManager
from backend.app.data.entity_resolver import EntityResolver, resolve_corner, load_corner_nicknames
from backend.app.config import settings


@pytest.fixture(scope="module")
def loaded_duckdb():
    mgr = DuckDBManager(db_path=":memory:", csv_dir=settings.KAGGLE_DATA_DIR)
    mgr.ingest_all_csvs()
    return mgr


@pytest.fixture(scope="module")
def resolver(loaded_duckdb):
    return EntityResolver(duckdb_manager=loaded_duckdb)


def test_corner_nicknames_loaded():
    """Verifies that corner nicknames are loaded correctly from JSON."""
    corners = load_corner_nicknames()
    assert len(corners) >= 20
    nicknames = [c["nickname"] for c in corners]
    assert "Copse" in nicknames
    assert "Eau Rouge" in nicknames
    assert "Parabolica" in nicknames
    assert "130R" in nicknames


def test_resolve_corner_by_nickname():
    """Verifies corner resolution by nickname and circuit."""
    # Silverstone Copse
    c1 = resolve_corner("silverstone", "Copse")
    assert c1 is not None
    assert c1["turn_number"] == 9
    assert c1["distance_m"] == 2980.0

    # Spa Eau Rouge
    c2 = resolve_corner("spa", "Eau Rouge")
    assert c2 is not None
    assert c2["turn_number"] == 2

    # Monza Parabolica
    c3 = resolve_corner("monza", "Parabolica")
    assert c3 is not None
    assert c3["turn_number"] == 11


def test_resolve_corner_by_turn_number():
    """Verifies corner resolution by turn number."""
    c = resolve_corner("silverstone", 9)
    assert c is not None
    assert c["turn_number"] == 9
    assert c["nickname"] == "Copse"

    c_str = resolve_corner("silverstone", "Turn 9")
    assert c_str is not None
    assert c_str["turn_number"] == 9


def test_resolve_driver_exact_and_fuzzy(resolver):
    """Verifies driver resolution by code, full name, surname, and forename."""
    # 3-letter code
    d_ver = resolver.resolve_driver("VER")
    assert d_ver is not None
    assert d_ver["surname"] == "Verstappen"

    # Full name
    d_ham = resolver.resolve_driver("Lewis Hamilton")
    assert d_ham is not None
    assert d_ham["code"] == "HAM"

    # Surname
    d_lec = resolver.resolve_driver("Leclerc")
    assert d_lec is not None
    assert d_lec["code"] == "LEC"

    # Fuzzy match
    d_nor = resolver.resolve_driver("Lando")
    assert d_nor is not None
    assert d_nor["code"] == "NOR"


def test_resolve_circuit_exact_and_fuzzy(resolver):
    """Verifies circuit resolution by circuitRef, name, location, and country."""
    # CircuitRef
    c_sil = resolver.resolve_circuit("silverstone")
    assert c_sil is not None
    assert c_sil["circuitRef"] == "silverstone"

    # Name
    c_spa = resolver.resolve_circuit("Spa-Francorchamps")
    assert c_spa is not None
    assert "Spa" in c_spa["name"]

    # Fuzzy / country
    c_monza = resolver.resolve_circuit("Monza")
    assert c_monza is not None
    assert "Monza" in c_monza["name"]
