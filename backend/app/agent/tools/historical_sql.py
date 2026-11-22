"""
Historical SQL Tool for PitWall AI Race Engineer.
Executes read-only queries against DuckDB views and automatically builds
dark HUD Plotly charts when applicable.
"""

from typing import Any, Dict, Optional
from backend.app.data.duckdb_manager import get_duckdb_manager, validate_sql
from backend.app.charts.historical_charts import auto_build_historical_chart


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
