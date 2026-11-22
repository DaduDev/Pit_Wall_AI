"""
Integration tests for Historical SQL Tool execution.
Validates:
- Execution of valid SQL queries against DuckDB views.
- Proper calculation of execution metrics (row count, execution_time_ms).
- Safe handling and rejection of forbidden SQL mutations.
- Automatic Plotly chart construction for historical data.
"""

import pytest
from backend.app.agent.tools.historical_sql import query_historical_f1
from backend.app.data.duckdb_manager import get_duckdb_manager
from backend.app.config import settings


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    mgr = get_duckdb_manager()
    conn = mgr.get_connection()
    res = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'results'").fetchone()
    if res and res[0] == 0:
        mgr.ingest_all_csvs(settings.KAGGLE_DATA_DIR)
    mgr.create_views()


def test_query_historical_f1_bahrain_2023():
    """Independent Test 1: Query 'Who won the 2023 Bahrain Grand Prix?'"""
    sql = """
        SELECT year, round, grand_prix, driver_code, surname, constructor, position, points
        FROM v_race_results
        WHERE year = 2023 AND grand_prix = 'Bahrain Grand Prix' AND position = 1
    """
    result = query_historical_f1(sql, chart_title="2023 Bahrain Grand Prix Winner")
    assert result["success"] is True
    assert result["row_count"] == 1
    assert result["execution_time_ms"] > 0
    winner = result["data"][0]
    assert winner["driver_code"] == "VER"
    assert winner["surname"] == "Verstappen"
    assert winner["constructor"] == "Red Bull"
    assert winner["points"] == 25


def test_query_historical_f1_hamilton_podiums():
    """Independent Test 2: Query Lewis Hamilton's podium finishes per season."""
    sql = """
        SELECT year, count(*) AS podiums
        FROM v_race_results
        WHERE driver_code = 'HAM' AND position <= 3
        GROUP BY year
        ORDER BY year ASC
    """
    result = query_historical_f1(sql, chart_title="Lewis Hamilton Podiums per Season")
    assert result["success"] is True
    assert result["row_count"] > 10
    # Confirm chart was automatically built (Line chart over years)
    assert result["chart"] is not None
    assert result["chart"]["chart_type"] in ["line", "bar"]
    assert "spec" in result["chart"]


def test_query_historical_f1_rejects_mutation():
    """Confirms mutating statement is caught and returned as clean error without crashing."""
    sql = "DROP TABLE results"
    result = query_historical_f1(sql)
    assert result["success"] is False
    assert result["error"] is not None
    assert "Forbidden mutating keyword" in result["error"] or "Only SELECT or WITH" in result["error"]
