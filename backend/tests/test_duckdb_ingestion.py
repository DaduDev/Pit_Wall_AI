r"""
Unit & Integration tests for DuckDB Kaggle CSV Ingestion and Curated Views.
Validates:
- All 14 CSV files ingested with positive row counts.
- '\N' string sentinels are converted to NULL.
- Curated views (v_race_results, v_qualifying, v_pit_stops, v_driver_standings, v_constructor_standings)
  are populated and queryable.
"""

import pytest
from backend.app.data.duckdb_manager import DuckDBManager
from backend.app.config import settings


@pytest.fixture(scope="module")
def duckdb_instance():
    """In-memory DuckDB manager loaded with actual Kaggle dataset."""
    mgr = DuckDBManager(db_path=":memory:", csv_dir=settings.KAGGLE_DATA_DIR)
    mgr.ingest_all_csvs()
    mgr.create_views()
    return mgr


def test_all_14_tables_ingested(duckdb_instance):
    """Verifies that all 14 Kaggle CSV files were successfully ingested."""
    expected_tables = [
        "circuits", "constructors", "constructor_results", "constructor_standings",
        "drivers", "driver_standings", "lap_times", "pit_stops", "qualifying",
        "races", "results", "seasons", "sprint_results", "status"
    ]
    conn = duckdb_instance.get_connection()
    tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
    
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' not found in DuckDB"
        count = conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        assert count > 0, f"Table '{table}' has 0 rows"


def test_backslash_n_converted_to_null(duckdb_instance):
    r"""
    Verifies that Kaggle '\N' tokens are converted to NULL sentinels
    and do not remain as literal string '\N'.
    """
    conn = duckdb_instance.get_connection()

    # 1. results.milliseconds contains \N for DNF drivers
    res_null_ms = conn.execute("SELECT count(*) FROM results WHERE milliseconds IS NULL").fetchone()[0]
    assert res_null_ms > 0, r"Expected NULL values in results.milliseconds where \N was normalized"

    # Verify no literal string '\N' exists in results.time or results.milliseconds
    res_str_backslash_n = conn.execute(r"SELECT count(*) FROM results WHERE time = '\N'").fetchone()[0]
    assert res_str_backslash_n == 0, r"Literal string '\N' found in results.time"

    # 2. drivers.code contains \N for older historical drivers
    code_nulls = conn.execute("SELECT count(*) FROM drivers WHERE code IS NULL").fetchone()[0]
    assert code_nulls > 0, r"Expected NULL values in drivers.code for older drivers"

    code_str_backslash_n = conn.execute(r"SELECT count(*) FROM drivers WHERE code = '\N'").fetchone()[0]
    assert code_str_backslash_n == 0, r"Literal string '\N' found in drivers.code"


def test_v_race_results_view(duckdb_instance):
    """Verifies v_race_results view queries successfully and returns expected columns."""
    res = duckdb_instance.execute_query("""
        SELECT year, round, grand_prix, driver_code, surname, constructor, position, points
        FROM v_race_results
        WHERE year = 2023 AND round = 1 AND position = 1
    """)
    assert res["row_count"] == 1
    row = res["data"][0]
    assert row["year"] == 2023
    assert row["driver_code"] == "VER"
    assert row["surname"] == "Verstappen"
    assert row["constructor"] == "Red Bull"
    assert row["position"] == 1


def test_v_qualifying_view(duckdb_instance):
    """Verifies v_qualifying view queries successfully."""
    res = duckdb_instance.execute_query("""
        SELECT year, round, grand_prix, driver_code, position, q3
        FROM v_qualifying
        WHERE year = 2023 AND position = 1
        ORDER BY round ASC
        LIMIT 1
    """)
    assert res["row_count"] == 1
    assert res["data"][0]["position"] == 1


def test_v_pit_stops_view(duckdb_instance):
    """Verifies v_pit_stops view queries successfully."""
    res = duckdb_instance.execute_query("""
        SELECT year, grand_prix, driver_code, stop, lap, duration
        FROM v_pit_stops
        WHERE year = 2023
        LIMIT 5
    """)
    assert res["row_count"] == 5
    for r in res["data"]:
        assert r["stop"] >= 1
        assert r["lap"] >= 1


def test_v_driver_standings_view(duckdb_instance):
    """Verifies v_driver_standings view queries successfully."""
    res = duckdb_instance.execute_query("""
        SELECT year, grand_prix, driver_code, surname, points, position, wins
        FROM v_driver_standings
        WHERE year = 2023 AND position = 1
        ORDER BY round DESC
        LIMIT 1
    """)
    assert res["row_count"] == 1
    winner = res["data"][0]
    assert winner["surname"] == "Verstappen"
    assert winner["position"] == 1
    assert winner["points"] >= 500


def test_v_constructor_standings_view(duckdb_instance):
    """Verifies v_constructor_standings view queries successfully."""
    res = duckdb_instance.execute_query("""
        SELECT year, grand_prix, constructor, points, position, wins
        FROM v_constructor_standings
        WHERE year = 2023 AND position = 1
        ORDER BY round DESC
        LIMIT 1
    """)
    assert res["row_count"] == 1
    champ = res["data"][0]
    assert champ["constructor"] == "Red Bull"
    assert champ["position"] == 1
