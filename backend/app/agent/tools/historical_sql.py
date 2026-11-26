"""
Historical SQL Tool for PitWall AI Race Engineer.
Executes read-only queries against DuckDB views and automatically builds
dark HUD Plotly charts when applicable.
"""

import re
from typing import Any, Dict, Optional
from backend.app.data.duckdb_manager import get_duckdb_manager, validate_sql
from backend.app.charts.historical_charts import auto_build_historical_chart


def _attempt_zero_row_correction(sql: str) -> Optional[str]:
    """
    Attempts to rewrite a query that returned 0 rows due to circuit/country aliases.
    E.g. if the query filters on lower(grand_prix) LIKE '%brazil%', expands to include
    circuit_country = 'Brazil' or grand_prix LIKE '%São Paulo%'.
    """
    sql_lower = sql.lower()

    # Brazil / Interlagos / São Paulo
    if "brazil" in sql_lower:
        pattern = re.compile(
            r"(?:"
            r"(?:lower\s*\(\s*(?:(?P<a1>\w+)\.)?grand_prix\s*\)|(?:(?P<a2>\w+)\.)?grand_prix)\s+(?:i?like)\s+'%brazil[^']*%'"
            r"|"
            r"(?:lower\s*\(\s*(?:(?P<a3>\w+)\.)?grand_prix\s*\)|(?:(?P<a4>\w+)\.)?grand_prix)\s*=\s*'(?:brazilian|brazil)\s+grand\s+prix'"
            r"|"
            r"(?:lower\s*\(\s*(?:(?P<a5>\w+)\.)?circuit_country\s*\)|(?:(?P<a6>\w+)\.)?circuit_country)\s*=\s*'brazil'"
            r")",
            re.IGNORECASE,
        )
        def _build_brazil_predicate(alias: str | None) -> str:
            pfx = f"{alias}." if alias else ""
            return (
                f"(lower({pfx}grand_prix) LIKE '%brazil%' OR "
                f"lower({pfx}grand_prix) LIKE '%são paulo%' OR "
                f"lower({pfx}circuit_country) = 'brazil')"
            )
        corrected = pattern.sub(
            lambda m: _build_brazil_predicate(
                m.group("a1") or m.group("a2") or m.group("a3") or m.group("a4") or m.group("a5") or m.group("a6")
            ),
            sql,
        )
        if corrected != sql:
            return corrected

    # Mexico
    if "mexico" in sql_lower:
        pattern = r"lower\(grand_prix\)\s+like\s+'%mexico%'"
        replacement = "(lower(grand_prix) LIKE '%mexico%' OR lower(circuit_country) = 'mexico')"
        corrected = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
        if corrected != sql:
            return corrected

    # Britain / UK
    if "britain" in sql_lower or "british" in sql_lower:
        pattern = r"lower\(grand_prix\)\s+like\s+'%(?:britain|british)%'"
        replacement = "(lower(grand_prix) LIKE '%british%' OR lower(circuit_country) IN ('uk', 'united kingdom'))"
        corrected = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
        if corrected != sql:
            return corrected

    # Italy / Monza / Imola
    if "italy" in sql_lower or "italian" in sql_lower:
        pattern = r"lower\(grand_prix\)\s+like\s+'%(?:italy|italian)%'"
        replacement = "(lower(grand_prix) LIKE '%italian%' OR lower(grand_prix) LIKE '%emilia%' OR lower(circuit_country) = 'italy')"
        corrected = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
        if corrected != sql:
            return corrected

    return None


def query_historical_f1(
    sql: str,
    chart_title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes a read-only DuckDB SQL query against Formula 1 historical views.
    
    Available curated views:
    - v_race_results (1950–2024 race results with finishing position, time, points, grid, constructor, circuit)
    - v_qualifying (qualifying results and Q1, Q2, Q3 lap times)
    - v_pit_stops (pit stop order, lap number, duration in seconds/ms)
    - v_driver_standings (driver points, championship position, and win counts after each race)
    - v_constructor_standings (constructor points, position, and win counts after each race)
    
    Parameters:
    - sql: The SELECT or WITH SQL statement to execute.
    - chart_title: Optional title for the auto-generated Plotly visualization.
    
    Returns:
    - Dictionary with columns, data rows, row_count, execution_time_ms, and optional chart spec.
    """
    db = get_duckdb_manager()

    try:
        # Validate read-only guardrails
        validate_sql(sql)

        # Execute query
        result = db.execute_query(sql)

        # Automatic zero-row self-correction for circuit/country aliases
        if result["row_count"] == 0:
            corrected_sql = _attempt_zero_row_correction(sql)
            if corrected_sql and corrected_sql != sql:
                try:
                    validate_sql(corrected_sql)
                    corrected_res = db.execute_query(corrected_sql)
                    if corrected_res["row_count"] > 0:
                        result = corrected_res
                        sql = corrected_sql
                except Exception:
                    pass

        # Generate Plotly chart if data is suitable
        chart_spec = auto_build_historical_chart(
            sql=sql,
            columns=result["columns"],
            data=result["data"],
            title_hint=chart_title,
        )

        return {
            "success": True,
            "sql": result["sql"],
            "row_count": result["row_count"],
            "execution_time_ms": result["execution_time_ms"],
            "columns": result["columns"],
            "data": result["data"][:50],  # Limit to 50 rows for LLM context efficiency
            "chart": chart_spec,
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "execution_time_ms": 0.0,
            "columns": [],
            "data": [],
            "chart": None,
            "error": str(e),
        }
