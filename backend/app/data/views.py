"""
Views module for PitWall AI.
Defines the 5 curated read-only DuckDB SQL views for Formula 1 historical data.
"""

V_RACE_RESULTS_SQL = """
CREATE OR REPLACE VIEW v_race_results AS
SELECT
    r.year, r.round, r.name AS grand_prix, r.date AS race_date,
    c.name AS circuit, c.country,
    d.code AS driver_code, d.forename, d.surname, d.nationality AS driver_nationality,
    con.name AS constructor, con.nationality AS constructor_nationality,
    res.grid, res.position, res.positionText, res.points, res.laps,
    res.time AS finish_time, res.milliseconds AS finish_ms,
    res.fastestLap, res.fastestLapTime, res.fastestLapSpeed,
    s.status
FROM results res
JOIN races r ON res.raceId = r.raceId
JOIN drivers d ON res.driverId = d.driverId
JOIN constructors con ON res.constructorId = con.constructorId
JOIN circuits c ON r.circuitId = c.circuitId
JOIN status s ON res.statusId = s.statusId;
"""

V_QUALIFYING_SQL = """
CREATE OR REPLACE VIEW v_qualifying AS
SELECT
    r.year, r.round, r.name AS grand_prix,
    d.code AS driver_code, d.forename, d.surname,
    con.name AS constructor,
    q.position, q.q1, q.q2, q.q3
FROM qualifying q
JOIN races r ON q.raceId = r.raceId
JOIN drivers d ON q.driverId = d.driverId
JOIN constructors con ON q.constructorId = con.constructorId;
"""

V_PIT_STOPS_SQL = """
CREATE OR REPLACE VIEW v_pit_stops AS
SELECT
    r.year, r.round, r.name AS grand_prix,
    d.code AS driver_code, d.surname,
    con.name AS constructor,
    ps.stop, ps.lap, ps.duration, ps.milliseconds AS duration_ms
FROM pit_stops ps
JOIN races r ON ps.raceId = r.raceId
JOIN drivers d ON ps.driverId = d.driverId
JOIN constructors con ON (
    SELECT res.constructorId FROM results res
    WHERE res.raceId = ps.raceId AND res.driverId = ps.driverId
    LIMIT 1
) = con.constructorId;
"""

V_DRIVER_STANDINGS_SQL = """
CREATE OR REPLACE VIEW v_driver_standings AS
SELECT
    r.year, r.round, r.name AS grand_prix,
    d.code AS driver_code, d.forename, d.surname,
    ds.points, ds.position, ds.wins
FROM driver_standings ds
JOIN races r ON ds.raceId = r.raceId
JOIN drivers d ON ds.driverId = d.driverId;
"""

V_CONSTRUCTOR_STANDINGS_SQL = """
CREATE OR REPLACE VIEW v_constructor_standings AS
SELECT
    r.year, r.round, r.name AS grand_prix,
    con.name AS constructor, con.nationality AS constructor_nationality,
    cs.points, cs.position, cs.wins
FROM constructor_standings cs
JOIN races r ON cs.raceId = r.raceId
JOIN constructors con ON cs.constructorId = con.constructorId;
"""

ALL_VIEWS_SQL = [
    ("v_race_results", V_RACE_RESULTS_SQL),
    ("v_qualifying", V_QUALIFYING_SQL),
    ("v_pit_stops", V_PIT_STOPS_SQL),
    ("v_driver_standings", V_DRIVER_STANDINGS_SQL),
    ("v_constructor_standings", V_CONSTRUCTOR_STANDINGS_SQL),
]

def create_curated_views(conn) -> list[str]:
    """Creates the 5 curated views in the provided DuckDB connection."""
    created = []
    for name, sql in ALL_VIEWS_SQL:
        conn.execute(sql)
        created.append(name)
    return created
