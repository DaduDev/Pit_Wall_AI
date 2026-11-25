"""
Shared Schema and Contract Tests for PitWall AI Chart SSE Payloads.
Asserts that chart SSE payloads across ALL 4 tool paths:
1. Historical SQL
2. Corner Telemetry Comparison
3. Full-Lap Telemetry Overlay
4. Tyre Stint Degradation & Strategy

Adhere to the standardized payload contract:
- Valid JSON with zero NaN or Infinity tokens.
- Envelope has chart_type, spec (with data array & layout object), caption, and metadata.
- metadata adheres to:
  { domain, year, grand_prix, session_name, mode_label, drivers: [{ code, name, color, compound? }], track_status? }
- drivers list elements are standardized dicts (never raw un-bracketed child objects or plain strings).
"""

import json
import re
from typing import Any, Dict
import pytest

from backend.app.chat.streaming import format_chart_event
from backend.app.agent.tools.historical_sql import query_historical_f1
from backend.app.agent.tools.corner_compare import compare_corner_telemetry
from backend.app.agent.tools.telemetry import compare_full_lap_telemetry
from backend.app.agent.tools.strategy import analyze_tyre_stints


def assert_valid_chart_sse_envelope(sse_str: str) -> Dict[str, Any]:
    """
    Validates that an SSE chart event string meets the strict PitWall AI contract:
    - Starts with 'event: chart\n'
    - Contains valid JSON data
    - Zero NaN / Infinity tokens
    - spec.data is a list
    - spec.layout is a dict
    - metadata.drivers is a list of standardized driver dicts (or empty for historical)
    """
    assert sse_str.startswith("event: chart\n"), "SSE event must be of type 'chart'"
    
    # Extract data payload
    data_match = re.search(r"data:\s*(.+?)(?:\n\n|$)", sse_str, re.DOTALL)
    assert data_match, "SSE event must contain data payload"
    raw_json = data_match.group(1).strip()

    # Assert zero invalid NaN/Infinity tokens
    assert "NaN" not in raw_json, "Payload must not contain raw NaN token (invalid JSON)"
    assert "Infinity" not in raw_json, "Payload must not contain Infinity token"

    payload = json.loads(raw_json)
    assert isinstance(payload, dict), "Payload must be a JSON object"
    assert "chart_type" in payload, "Payload missing 'chart_type'"
    assert "spec" in payload, "Payload missing 'spec'"
    assert "metadata" in payload, "Payload missing 'metadata'"

    spec = payload["spec"]
    assert isinstance(spec, dict), "spec must be an object"
    assert isinstance(spec.get("data"), list), "spec.data must be a list"
    assert isinstance(spec.get("layout"), dict), "spec.layout must be a dict"

    meta = payload["metadata"]
    assert isinstance(meta, dict), "metadata must be an object"
    assert meta.get("domain") in ("historical", "telemetry"), f"Invalid domain: {meta.get('domain')}"
    assert "mode_label" in meta and isinstance(meta["mode_label"], str), "mode_label must be a string"
    assert isinstance(meta.get("drivers"), list), "metadata.drivers must be a list"

    for drv in meta["drivers"]:
        assert isinstance(drv, dict), f"Each driver must be a dict, got: {type(drv)}"
        assert "code" in drv, "Driver object must have 'code'"
        assert isinstance(drv["code"], str) and len(drv["code"]) > 0, "Driver code must be non-empty string"
        assert "color" in drv, "Driver object must have 'color'"

    return payload


def test_contract_historical_sql_chart_payload():
    """Validates contract for Historical SQL charts (horizontal ranking bar / table)."""
    sql = (
        "SELECT driver_name, "
        "COUNT(DISTINCT race_id) AS total_starts, "
        "COUNT(DISTINCT CASE WHEN position = 1 THEN race_id END) AS wins, "
        "ROUND(COUNT(DISTINCT CASE WHEN position = 1 THEN race_id END) * 100.0 / COUNT(DISTINCT race_id), 2) AS win_percentage "
        "FROM v_race_results "
        "WHERE lower(circuit) LIKE '%monza%' "
        "GROUP BY driver_id, driver_name "
        "HAVING COUNT(DISTINCT race_id) >= 5 "
        "ORDER BY win_percentage DESC LIMIT 10;"
    )
    res = query_historical_f1(sql, chart_title="Monza Win Percentage Leaderboard")
    assert res["success"] is True
    assert res["chart"] is not None

    chart_dict = res["chart"]
    sse_output = format_chart_event(
        chart_type=chart_dict["chart_type"],
        spec=chart_dict["spec"],
        caption=chart_dict.get("caption", "Monza Win Percentage"),
        metadata=chart_dict.get("metadata"),
    )
    payload = assert_valid_chart_sse_envelope(sse_output)
    assert payload["metadata"]["domain"] == "historical"
    assert payload["metadata"]["drivers"] == []


def test_contract_corner_telemetry_chart_payload():
    """Validates contract for Corner-by-Corner Telemetry comparison charts."""
    res = compare_corner_telemetry(
        driver1="VER",
        driver2="NOR",
        corner="Turn 1",
        grand_prix="Monza",
        year=2024,
    )
    assert res["success"] is True
    assert res["chart"] is not None

    sse_output = format_chart_event(
        chart_type=res["chart"]["chart_type"],
        spec=res["chart"]["spec"],
        caption=res["chart"]["caption"],
        metadata=res["chart"].get("metadata"),
    )
    payload = assert_valid_chart_sse_envelope(sse_output)
    assert payload["chart_type"] == "corner_comparison"
    assert payload["metadata"]["domain"] == "telemetry"
    driver_codes = [d["code"] for d in payload["metadata"]["drivers"]]
    assert driver_codes == ["VER", "NOR"]


def test_contract_full_lap_telemetry_chart_payload():
    """Validates contract for Full-Lap Telemetry Overlay comparison charts."""
    res = compare_full_lap_telemetry(
        driver1="VER",
        driver2="NOR",
        grand_prix="Monza",
        year=2024,
    )
    assert "chart" in res
    assert res["chart"] is not None

    sse_output = format_chart_event(
        chart_type=res["chart"]["chart_type"],
        spec=res["chart"]["spec"],
        caption=res["chart"]["caption"],
        metadata=res["chart"].get("metadata"),
    )
    payload = assert_valid_chart_sse_envelope(sse_output)
    assert payload["chart_type"] == "full_lap_comparison"
    assert payload["metadata"]["domain"] == "telemetry"
    assert "sector_summary" in payload["metadata"]
    driver_codes = [d["code"] for d in payload["metadata"]["drivers"]]
    assert driver_codes == ["VER", "NOR"]


def test_contract_tyre_stint_strategy_chart_payload():
    """Validates contract for Tyre Stint Degradation & Strategy charts."""
    res = analyze_tyre_stints(
        year=2024,
        grand_prix="Monza",
        drivers=["LEC", "PIA"],
    )
    assert "chart" in res
    assert res["chart"] is not None

    sse_output = format_chart_event(
        chart_type=res["chart"]["chart_type"],
        spec=res["chart"]["spec"],
        caption=res["chart"]["caption"],
        metadata=res["chart"].get("metadata"),
    )
    payload = assert_valid_chart_sse_envelope(sse_output)
    assert payload["chart_type"] == "tyre_degradation"
    assert payload["metadata"]["domain"] == "telemetry"
    driver_codes = [d["code"] for d in payload["metadata"]["drivers"]]
    assert driver_codes == ["LEC", "PIA"]
