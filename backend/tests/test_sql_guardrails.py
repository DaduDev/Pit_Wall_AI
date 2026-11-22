"""
Unit tests for Read-Only SQL Guardrails.
Validates:
- Safe SELECT / WITH statements are allowed.
- Mutating statements (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE) are rejected.
- Multi-statement injection attempts are rejected.
"""

import pytest
from backend.app.data.duckdb_manager import validate_sql, DuckDBManager


def test_valid_select_queries_allowed():
    """Confirms legitimate read-only queries pass validation."""
    valid_queries = [
        "SELECT * FROM v_race_results WHERE year = 2023;",
        "SELECT driver_code, count(*) FROM results GROUP BY driver_code",
        """
        WITH top_drivers AS (
            SELECT driverId, count(*) as wins FROM results WHERE position = 1 GROUP BY driverId
        )
        SELECT * FROM top_drivers ORDER BY wins DESC LIMIT 10;
        """,
        "   select forename, surname from drivers where nationality = 'British'   ",
    ]
    for q in valid_queries:
        validate_sql(q)  # Should not raise


def test_empty_queries_rejected():
    """Confirms empty or whitespace queries are rejected."""
    with pytest.raises(ValueError, match="empty|No valid SQL statement"):
        validate_sql("")
    with pytest.raises(ValueError, match="empty|No valid SQL statement"):
        validate_sql("   -- just a comment\n  ")


@pytest.mark.parametrize("keyword", [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", 
    "CREATE", "REPLACE", "ATTACH", "DETACH", "COPY", "PRAGMA", "CALL"
])
def test_mutating_keywords_rejected(keyword):
    """Confirms that any mutating SQL keywords trigger an immediate rejection."""
    evil_query = f"{keyword} TABLE results"
    with pytest.raises(ValueError, match="Only SELECT or WITH|Forbidden mutating keyword"):
        validate_sql(evil_query)

    evil_nested = f"SELECT * FROM v_race_results; {keyword} TABLE test"
    with pytest.raises(ValueError, match="Multiple SQL statements|Forbidden mutating keyword"):
        validate_sql(evil_nested)


def test_statement_stacking_rejected():
    """Confirms multiple statements separated by ';' are rejected."""
    stacked = "SELECT 1; DROP TABLE results;"
    with pytest.raises(ValueError, match="Multiple SQL statements"):
        validate_sql(stacked)


def test_duckdb_manager_execution_blocks_mutations():
    """Confirms DuckDBManager.execute_query enforces guardrails end-to-end."""
    mgr = DuckDBManager(db_path=":memory:")
    
    # Should execute safe query
    res = mgr.execute_query("SELECT 42 AS answer")
    assert res["data"][0]["answer"] == 42
    assert res["execution_time_ms"] >= 0

    # Should block drop table
    with pytest.raises(ValueError):
        mgr.execute_query("DROP TABLE results")
