"""
Pytest Regression Test for Historical SQL Win Percentage and Horizontal Ranking Chart.
Validates:
- Monza >= 5 starts query accuracy:
  - Juan Manuel Fangio ranks #1 (3 wins / 7 distinct starts = 42.86%)
  - Juan Pablo Montoya ranks #2 (2 wins / 5 starts = 40.0%)
  - Alberto Ascari ranks #3 (2 wins / 5 starts = 40.0%)
- Plotly chart generation:
  - Uses driver_name as category labels with zero 'None' or NULL labels.
  - Plots win_percentage as the numeric metric (not total_starts).
  - Uses horizontal bar orientation ('h') with textposition='outside' and autorange='reversed'.
"""

import pytest
from backend.app.agent.tools.historical_sql import query_historical_f1
from backend.app.data.duckdb_manager import get_duckdb_manager


@pytest.fixture(scope="module", autouse=True)
def ensure_db_views():
    mgr = get_duckdb_manager()
    mgr.create_views()


def test_monza_win_percentage_regression():
    sql = """
    SELECT 
        driver_name,
        COUNT(DISTINCT race_id) AS total_starts,
        COUNT(DISTINCT CASE WHEN position = 1 THEN race_id END) AS wins,
        ROUND(COUNT(DISTINCT CASE WHEN position = 1 THEN race_id END) * 100.0 / COUNT(DISTINCT race_id), 2) AS win_percentage
    FROM v_race_results
    WHERE lower(circuit) LIKE '%monza%'
      AND status NOT IN ('Did not qualify', 'Did not prequalify', 'Did not start', 'Withdrew')
    GROUP BY driver_id, driver_name
    HAVING COUNT(DISTINCT race_id) >= 5
    ORDER BY win_percentage DESC, wins DESC, total_starts ASC, driver_id ASC
    LIMIT 15;
    """

    res = query_historical_f1(sql, chart_title="Monza Win Percentage (Min 5 Starts)")

    assert res["success"] is True, f"Query failed: {res.get('error')}"
    data = res["data"]
    assert len(data) >= 3

    # 1. Assert Juan Manuel Fangio ranks #1 (3 wins / 7 distinct starts = 42.86%)
    p1 = data[0]
    assert "Fangio" in p1["driver_name"], f"Expected Fangio at P1, got {p1['driver_name']}"
    assert p1["wins"] == 3
    assert p1["total_starts"] == 7
    assert p1["win_percentage"] == 42.86

    # 2. Assert Juan Pablo Montoya ranks #2 (2 wins / 5 distinct starts = 40.0%)
    p2 = data[1]
    assert p2["driver_name"] == "Juan Pablo Montoya"
    assert p2["wins"] == 2
    assert p2["total_starts"] == 5
    assert p2["win_percentage"] == 40.0

    # 3. Assert Alberto Ascari ranks #3 (2 wins / 5 distinct starts = 40.0%)
    p3 = data[2]
    assert p3["driver_name"] == "Alberto Ascari"
    assert p3["wins"] == 2
    assert p3["total_starts"] == 5
    assert p3["win_percentage"] == 40.0

    # 4. Assert Plotly JSON Chart properties
    chart = res.get("chart")
    assert chart is not None, "Plotly chart was not generated"
    assert chart["chart_type"] == "bar"

    spec = chart["spec"]
    trace = spec["data"][0]

    # Verify horizontal ranking configuration
    assert trace["type"] == "bar"
    assert trace["orientation"] == "h", "Chart should be horizontal ranking bar chart"
    assert trace["textposition"] == "outside", "Text labels must be positioned outside the bars"
    assert spec["layout"]["yaxis"]["autorange"] == "reversed", "Y-axis should have autorange='reversed' so #1 is at top"

    # Verify category labels use driver_name with zero 'None'
    categories = trace["y"]
    assert "None" not in categories
    assert None not in categories
    assert any("Fangio" in c for c in categories)
    assert "Juan Pablo Montoya" in categories
    assert "Alberto Ascari" in categories

    # Verify numeric metric values plot win_percentage (42.86), NOT total_starts (7)
    values = trace["x"]
    assert values[0] == 42.86, f"Expected win_percentage 42.86 on x-axis, got {values[0]} (likely total_starts bug)"
    assert values[1] == 40.0
    assert values[2] == 40.0

    # Verify outside percentage label
    assert "42.9%" in trace["text"][0] or "42.86%" in trace["text"][0]
