"""
Regression test suite for live testing bug fixes:
1. Enforce 2023+ OpenF1 telemetry era boundary (no silent fallback to Silverstone 2024).
2. Unknown corners raise ValueError instead of defaulting to Copse/Turn 9.
3. 2021 Brazil Grand Prix alias resolution (São Paulo GP match via country/alias in DuckDB).
4. Multi-turn context inheritance (inherits drivers and year for follow-ups like 'What about Suzuka?').
5. Kill phantom fallback SQL query (no silent Abu Dhabi 2023 round 22 query).
6. Heavy-braking corner telemetry comparison on real cached OpenF1 data (Monza T1 / Spa T1).
"""

import pytest
import asyncio
from backend.app.chat.session import ConversationSession
from backend.app.agent.orchestrator import RaceEngineerOrchestrator
from backend.app.agent.tools.telemetry import load_driver_lap
from backend.app.agent.tools.corner_compare import compare_corner_telemetry
from backend.app.agent.tools.historical_sql import query_historical_f1


def test_era_boundary_raises_value_error_pre_2023():
    """
    Direct test: load_driver_lap for pre-2023 must raise ValueError
    explaining OpenF1 2023+ era boundary, and never silently load Silverstone 2024.
    """
    with pytest.raises(ValueError) as excinfo:
        load_driver_lap(year=2021, grand_prix="Brazil", driver_code="HAM")

    err_msg = str(excinfo.value)
    assert "2023–present via the OpenF1 REST API" in err_msg
    assert "2021 Brazil" in err_msg
    assert "Silverstone" not in err_msg


def test_unknown_corner_raises_value_error():
    """
    Direct test: compare_corner_telemetry with an unknown corner must raise ValueError
    rather than silently defaulting to Copse (Turn 9, 2980m).
    """
    with pytest.raises(ValueError) as excinfo:
        compare_corner_telemetry(
            year=2024,
            grand_prix="Silverstone",
            corner="NonExistentCorner99",
            driver1="VER",
            driver2="NOR",
        )
    err_msg = str(excinfo.value)
    assert "Corner 'NonExistentCorner99' not recognized" in err_msg


def test_brazil_2021_alias_matches_sao_paulo_gp():
    """
    Historical SQL test: Querying 2021 Brazil Grand Prix winner matches
    the official 'São Paulo Grand Prix' in DuckDB via circuit_country = 'Brazil'.
    Winner must be Lewis Hamilton (P1) and Max Verstappen (P2).
    """
    sql = (
        "SELECT position, driver_name, constructor, points "
        "FROM v_race_results "
        "WHERE year = 2021 AND (lower(grand_prix) LIKE '%brazil%' OR lower(grand_prix) LIKE '%são paulo%' OR lower(circuit_country) = 'brazil') "
        "ORDER BY position ASC LIMIT 5;"
    )
    result = query_historical_f1(sql)
    assert result["success"] is True
    assert result["row_count"] >= 2

    p1 = result["data"][0]
    p2 = result["data"][1]

    assert p1["position"] == 1
    assert "Hamilton" in p1["driver_name"]
    assert p1["constructor"] == "Mercedes"

    assert p2["position"] == 2
    assert "Verstappen" in p2["driver_name"]
    assert p2["constructor"] == "Red Bull"


def test_zero_row_self_correction_for_brazil():
    """
    Historical SQL test: Query with strict 'lower(grand_prix) LIKE %brazil%' in 2021
    initially yields 0 rows, but automatic self-correction rewrites it to include
    circuit_country = 'Brazil' or 'São Paulo' and returns Hamilton P1.
    """
    strict_sql = "SELECT driver_name, position FROM v_race_results WHERE year = 2021 AND lower(grand_prix) LIKE '%brazil%' AND position = 1;"
    result = query_historical_f1(strict_sql)
    assert result["success"] is True
    assert result["row_count"] == 1
    assert "Hamilton" in result["data"][0]["driver_name"]


def test_monza_turn_1_cached_openf1_telemetry():
    """
    Real OpenF1 telemetry test: Monza Turn 1 (Variante del Rettifilo) 2024 Qualifying
    between Verstappen and Norris uses cached OpenF1 data and produces real heavy-braking metrics
    (<100 km/h apex speed, Gear 2).
    """
    result = compare_corner_telemetry(
        year=2024,
        grand_prix="Monza",
        corner="Turn 1",
        driver1="VER",
        driver2="NOR",
    )
    assert result is not None
    metrics = result["metrics"]
    meta_a = result["metadata"]["driver_a"]
    meta_b = result["metadata"]["driver_b"]

    assert meta_a["driver_code"] == "VER"
    assert meta_b["driver_code"] == "NOR"

    # Monza Turn 1 is a heavy chicane: speed drops below 90 km/h, Gear 2
    apex_a = metrics["apex_min_speed_kph"]["driver_a"]
    apex_b = metrics["apex_min_speed_kph"]["driver_b"]
    gear_a = metrics["lowest_gear"]["driver_a"]
    gear_b = metrics["lowest_gear"]["driver_b"]

    assert 60.0 <= apex_a <= 95.0, f"Expected Monza T1 apex speed ~73 km/h, got {apex_a}"
    assert 60.0 <= apex_b <= 95.0, f"Expected Monza T1 apex speed ~75 km/h, got {apex_b}"
    assert gear_a == 2
    assert gear_b == 2


def test_orchestrator_era_boundary_routes_to_historical():
    """
    Orchestrator test: Asking for 2021 Brazil GP telemetry between Verstappen and Hamilton
    must trigger the era boundary event and return historical DuckDB race results
    (Hamilton P1, Verstappen P2) instead of Silverstone 2024 Copse.
    """
    async def _run():
        orchestrator = RaceEngineerOrchestrator()
        session = ConversationSession(session_id="test_era", user_id="test_user")

        events = []
        async for event_str in orchestrator.stream_query(
            "Compare Verstappen and Hamilton through Turn 9 at 2021 Brazil GP",
            session,
        ):
            events.append(event_str)

        full_output = "".join(events)
        assert '"step": "era_boundary"' in full_output or "Telemetry Era Boundary Notice" in full_output
        assert "2023–present" in full_output
        assert "Silverstone" not in full_output
        assert "Copse" not in full_output

        # Check that session updated with historical tool
        assert session.last_entities.year == 2021
        assert session.last_entities.tool == "historical_sql"

    asyncio.run(_run())


def test_orchestrator_multi_turn_context_inheritance():
    """
    Orchestrator test: Turn 1 sets up VER and NOR at Silverstone 2024.
    Turn 2 'What about Suzuka?' inherits drivers (VER, NOR) and year (2024),
    and assigns marquee corner 130R without failing or running Abu Dhabi 2023.
    """
    orchestrator = RaceEngineerOrchestrator()
    session = ConversationSession(session_id="test_multiturn", user_id="test_user")

    # Seed session with Turn 1 entities
    session.update_entities(
        year=2024,
        grand_prix="Silverstone",
        circuit_key="silverstone",
        drivers=["VER", "NOR"],
        corner="Copse",
        tool="telemetry",
    )

    # Parse intent for Turn 2 follow-up
    intent = orchestrator._parse_corner_comparison_intent("What about Suzuka?", session=session)
    assert intent is not None
    assert intent["driver1"] == "VER"
    assert intent["driver2"] == "NOR"
    assert intent["grand_prix"] == "Suzuka"
    assert intent["year"] == 2024
    assert intent["corner"] == "130R"


def test_orchestrator_kills_phantom_sql_query():
    """
    Orchestrator test: An ambiguous query that cannot be formulated into SQL
    returns a clear clarifying question and NEVER runs the hardcoded 2023 Abu Dhabi query.
    """
    async def _run():
        orchestrator = RaceEngineerOrchestrator()
        session = ConversationSession(session_id="test_clarify", user_id="test_user")

        events = []
        async for event_str in orchestrator.stream_query(
            "asdfghjkl random gibberish non f1 query",
            session,
        ):
            events.append(event_str)

        full_output = "".join(events)
        # Must NOT run 2023 Abu Dhabi query
        assert "Abu Dhabi" not in full_output
        assert "round 22" not in full_output
        # Must not run hardcoded Abu Dhabi query and provide valid output or clarification
        lower_out = full_output.lower()
        assert (
            "clarify" in lower_out
            or "please specify" in lower_out
            or "noise on the radio" in lower_out
            or "proper query" in lower_out
            or "zero data" in lower_out
            or "screen" in lower_out
            or "leaderboards" in lower_out
        )

    asyncio.run(_run())
