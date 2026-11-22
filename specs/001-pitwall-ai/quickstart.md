# Quickstart Validation Guide: PitWall AI

**Feature**: 001-pitwall-ai | **Date**: 2026-11-22

This guide provides runnable validation scenarios that prove each core capability works end-to-end. See [data-model.md](./data-model.md) for entity details and [contracts/api-contracts.md](./contracts/api-contracts.md) for API specifications.

## Prerequisites

- Python 3.12+
- Node.js 20+ and pnpm
- Kaggle F1 dataset CSVs in `backend/data/kaggle_csvs/`
- Internet access for initial FastF1 cache population (subsequent runs use disk cache)

## Setup Commands

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Ingest Kaggle CSVs into DuckDB (creates data/f1_data.duckdb)
python -m app.data.duckdb_manager

# Enable FastF1 cache
mkdir -p data/fastf1_cache
```

### Frontend

```bash
cd frontend
pnpm install
```

## Validation Scenarios

### V1: DuckDB Ingestion & \N Normalization

**What it proves**: Kaggle CSVs are correctly loaded with `\N` → NULL normalization. Read-only SQL views return accurate data.

**Run**:
```bash
cd backend
pytest tests/test_duckdb_ingestion.py -v
```

**Expected Outcome**:
- All `\N` values in source CSVs are stored as SQL NULL (not the string `\N`).
- `v_race_results` returns Max Verstappen as 2023 Bahrain GP winner.
- `v_qualifying` returns correct Q1/Q2/Q3 times for a known session.
- `v_pit_stops` returns correct pit stop counts and durations.
- `v_driver_standings` returns correct cumulative points.

### V2: Read-Only SQL Guardrails

**What it proves**: The SQL execution tool rejects all write operations, preventing data corruption.

**Run**:
```bash
cd backend
pytest tests/test_sql_guardrails.py -v
```

**Expected Outcome**:
- `INSERT INTO results ...` → rejected with error.
- `UPDATE drivers SET ...` → rejected with error.
- `DELETE FROM races ...` → rejected with error.
- `DROP TABLE results` → rejected with error.
- `SELECT * FROM v_race_results WHERE year = 2023` → succeeds with results.

### V3: Corner Slicing Math

**What it proves**: Telemetry interpolation and corner slicing produce correct metrics using the 2024 British GP Qualifying fixture.

**Run**:
```bash
cd backend
pytest tests/test_corner_slicing.py -v
```

**Expected Outcome**:
- Telemetry is interpolated to 1-meter distance grid.
- Corner window (±200m around Copse) correctly slices entry-apex-exit zone.
- Braking point delta, apex min speed, lowest gear, full-throttle pickup, and corner time delta are computed and match manually verified values from the same FastF1 data.
- GPS coordinates within the corner window are correct for mini-map rendering.

### V4: Entity Resolution

**What it proves**: Fuzzy matching correctly resolves natural-language driver/circuit/corner names.

**Run**:
```bash
cd backend
pytest tests/test_entity_resolver.py -v
```

**Expected Outcome**:
- "Verstappen" → `VER`, "Max" → `VER`, "max verstappen" → `VER`.
- "Silverstone" → correct circuit ID, "British Grand Prix" → correct circuit ID.
- "Copse" → Turn 9 at Silverstone, "Eau Rouge" → Turn 3 at Spa.
- Ambiguous input (e.g., just "Turn 3") prompts for circuit disambiguation.

### V5: Full Backend Integration (SSE Stream)

**What it proves**: The full pipeline — from natural-language input through LLM tool routing to Plotly chart output — works end-to-end with correct SSE events.

**Run**:
```bash
cd backend
# Start the server
uvicorn app.main:app --port 8000 &

# Test a historical query
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Authorization: Bearer <test-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Who won the 2023 Bahrain Grand Prix?"}'
```

**Expected Outcome**:
- SSE events arrive in order: `session` → `status` (1+) → `text` → `chart` → `trace` → `done`.
- `text` event contains "Max Verstappen" (or equivalent).
- `trace` event contains the exact SQL query executed.
- `chart` event contains valid Plotly JSON with dark HUD theme.

### V6: Frontend Smoke Test (Playwright)

**What it proves**: The React frontend renders Plotly charts correctly with zero console errors on the dark HUD background.

**Run**:
```bash
# Start backend
cd backend && uvicorn app.main:app --port 8000 &

# Start frontend
cd frontend && pnpm dev &

# Run Playwright
cd frontend && pnpm exec playwright test tests/smoke.spec.ts
```

**Expected Outcome**:
- Login page renders and accepts credentials.
- After login, the pit-wall layout renders (chat panel left, chart stage right).
- Submitting a test query produces a Plotly chart in the chart stage.
- The Engineering Trace drawer is accessible and shows query/telemetry params.
- Zero JavaScript console errors throughout the test.
- Background color of chart stage is `#0B0F17`.

### V7: Full pytest Suite

**What it proves**: All backend tests pass against real data fixtures.

**Run**:
```bash
cd backend
pytest -v --tb=short
```

**Expected Outcome**:
- All tests in `test_duckdb_ingestion.py`, `test_sql_guardrails.py`, `test_corner_slicing.py`, `test_entity_resolver.py`, `test_telemetry_tools.py`, `test_chart_builders.py`, and `test_prediction.py` pass.
- No synthetic mocks used for user-facing numerical computations.

## Constitution Compliance Verification

Each validation scenario maps to constitution principles:

| Scenario | Principle(s) Verified |
|----------|-----------------------|
| V1 | I (Zero-Hallucination: numbers from SQL), II (Data Domain Separation: DuckDB for historical) |
| V2 | I (read-only guardrail prevents data corruption) |
| V3 | I (deterministic NumPy computation), II (FastF1 for telemetry) |
| V4 | VII (metadata fidelity: correct entity resolution) |
| V5 | IV (Provenance: trace event), VII (metadata in chart events) |
| V6 | III (HUD Visual: #0B0F17 background), VI (Team Colors via Plotly) |
| V7 | V (Automated Verification: all features tested with real data) |
