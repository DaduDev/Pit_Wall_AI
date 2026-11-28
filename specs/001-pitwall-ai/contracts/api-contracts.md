# API Contracts: PitWall AI

**Feature**: 001-pitwall-ai | **Date**: 2026-11-22

## Base URL

```
http://localhost:8000/api
```

## Authentication

### POST /api/auth/login

Authenticate a user and receive a session token.

**Request Body**:
```json
{
  "email": "string",
  "password": "string"
}
```

**Response 200**:
```json
{
  "token": "string (JWT)",
  "user_id": "string (UUID)",
  "expires_at": "string (ISO 8601)"
}
```

**Response 401**:
```json
{
  "error": "Invalid credentials"
}
```

### POST /api/auth/register

Create a new user account.

**Request Body**:
```json
{
  "email": "string",
  "password": "string"
}
```

**Response 201**:
```json
{
  "user_id": "string (UUID)",
  "email": "string"
}
```

**Response 409**:
```json
{
  "error": "Email already registered"
}
```

---

## Chat (SSE Streaming)

### POST /api/chat/stream

Send a natural-language question and receive a streaming response via Server-Sent Events.

**Headers**:
```
Authorization: Bearer <JWT token>
Content-Type: application/json
Accept: text/event-stream
```

**Request Body**:
```json
{
  "message": "string",
  "session_id": "string (UUID, optional — omit to start new session)"
}
```

**Response**: `text/event-stream` with the following event types:

#### Event: `session`
Emitted once at the start. Provides the session ID for follow-up messages.
```
event: session
data: {"session_id": "uuid-string"}
```

#### Event: `status`
Emitted during data loading/computation. Provides streaming progress messages.
```
event: status
data: {"message": "Loading 2023 Belgian GP Qualifying session…"}
```

#### Event: `text`
Emitted for natural-language commentary from the AI race engineer.
```
event: text
data: {"content": "Verstappen brakes 12 meters later than Leclerc into Eau Rouge…", "done": false}
```
When `done: true`, the text stream is complete.

#### Event: `chart`
Emitted when a visualization or structured HUD card is ready. Always preserves top-level `viz_type`.
```
event: chart
data: {
  "chart_id": "string",
  "viz_type": "corner_telemetry | full_lap | tyre_stints | historical_sql | kpi_card | data_table | web_intelligence_card",
  "chart_type": "corner_comparison | full_lap_comparison | tyre_degradation | historical_sql | kpi_card | data_table | web_intelligence_card",
  "title": "Speed Comparison: VER vs LEC — Eau Rouge (2023 Belgian GP Q)",
  "caption": "string",
  "spec": { <Plotly figure JSON, KPI card spec, Data Table spec, or Web Intelligence card spec> },
  "figure": { <Plotly figure JSON when applicable> },
  "kpi_card": {
    "subtitle": "2021 Brazilian Grand Prix",
    "metrics": [{"label": "Winner", "value": "Lewis Hamilton"}]
  },
  "data_table": {
    "subtitle": "string",
    "columns": ["..."],
    "rows": [{"...": "..."}]
  },
  "web_intelligence_card": {
    "title": "string",
    "summary": "string",
    "bullets": ["..."],
    "sources": [{"title": "string", "url": "string"}]
  },
  "metadata": {
    "grand_prix": "Belgian Grand Prix",
    "year": 2023,
    "session": "Qualifying",
    "drivers": ["VER", "LEC"],
    "driver_1_lap_time": "1:12.000 (optional for full_lap)",
    "driver_2_lap_time": "1:12.000 (optional for full_lap)",
    "faster_driver": "RUS (optional for full_lap)",
    "laps": [1, 1],
    "compounds": ["SOFT", "SOFT"],
    "weather": "Dry"
  }
}
```

#### Event: `trace`
Emitted with provenance data for the Engineering Trace panel.
```
event: trace
data: {
  "data_domain": "historical | telemetry | research | mixed",
  "provider": "gemini | ollama_fallback | cache",
  "query": "SELECT ... FROM v_race_results WHERE ...",
  "dataset_id": "uuid-string",
  "a2a_hops": [ ... ],
  "grounding_sources": [{"title": "string", "url": "string"}],
  "grounded": true,
  "telemetry_params": {
    "year": 2023,
    "grand_prix": "Belgian Grand Prix",
    "session": "Q",
    "drivers": ["VER", "LEC"],
    "laps": [1, 1],
    "channels": ["Speed", "Throttle", "Brake", "nGear"],
    "corner": "Eau Rouge",
    "slice_range_m": [-200, 200]
  },
  "python_code": "# (only for ad-hoc Tier 2 charts)\nimport numpy as np\n..."
}
```

#### Event: `error`
Emitted on failure.
```
event: error
data: {
  "error": "string",
  "error_type": "data_unavailable | boundary_2018 | timeout | sandbox_violation | auth_expired | unknown",
  "suggestion": "string (optional — alternative analysis suggestion)"
}
```

#### Event: `done`
Emitted once at the end of the response. Signals the client to close the SSE connection.
```
event: done
data: {}
```

---

## Health Check

### GET /api/health

**Response 200**:
```json
{
  "status": "ok",
  "duckdb": "connected",
  "fastf1_cache": "ready",
  "tables_loaded": 10,
  "views_created": 4
}
```

---

## SSE Event Type Summary

| Event | Purpose | Cardinality |
|-------|---------|-------------|
| `session` | Provide session ID | Exactly once |
| `status` | Streaming progress | 0–N |
| `text` | AI commentary | 1–N (last has `done: true`) |
| `chart` | Plotly visualization | 0–N |
| `trace` | Engineering Trace | Exactly once |
| `error` | Error information | 0–1 |
| `done` | End of response | Exactly once |

## Error Codes

| error_type | HTTP Context | Description |
|------------|--------------|-------------|
| `data_unavailable` | 200 (SSE) | Requested data not found in DuckDB or FastF1 |
| `boundary_2018` | 200 (SSE) | Telemetry requested for pre-2018 season |
| `timeout` | 200 (SSE) | Sandbox execution or FastF1 load exceeded timeout |
| `sandbox_violation` | 200 (SSE) | Ad-hoc Python attempted forbidden operation |
| `auth_expired` | 401 | JWT token expired or invalid |
| `unknown` | 200 (SSE) | Unexpected server error |

## Request/Response Size Limits

- Maximum message length: 2000 characters
- Maximum Plotly JSON payload: 5 MB per chart event
- SSE connection timeout: 120 seconds (covers worst-case telemetry load + computation)
