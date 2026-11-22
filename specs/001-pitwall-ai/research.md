# Research: PitWall AI — F1 Race Engineer

**Feature**: 001-pitwall-ai | **Date**: 2026-11-22

All technical decisions were provided by the user. No NEEDS CLARIFICATION items remain. This document consolidates the rationale for each choice.

## R1: LLM Orchestration Framework

**Decision**: Google ADK (`google-adk`) with `gemini-3.5-flash-lite` (primary) and local Ollama (`ollama_chat/qwen3.5:4b`) fallback

**Rationale**: Google ADK provides a structured agent framework with native tool-calling, function declarations, and streaming support. `gemini-3.5-flash-lite` via Google AI Studio (`GOOGLE_API_KEY`) offers fast, cost-effective inference with strong code-generation capabilities. Configuring `thinking_level="low"` (or `"medium"` for complex multi-table queries) ensures multi-step tool calls execute completely without premature termination, omitting deprecated sampling parameters (`temperature`, `top_p`, `top_k`). For offline development and resilience against HTTP 429/503 quota limits, Google ADK's `LiteLlm` integration routes to a local Ollama instance (`ollama_chat/qwen3.5:4b`, `OLLAMA_API_BASE=http://localhost:11434`), trimming conversation history to the last 2 turns to operate within 8GB RAM. An `asyncio.Semaphore(3)` guard and response caching protect rate limits.

**Alternatives Considered**:
- LangChain/LangGraph: More ecosystem momentum but heavier abstraction; ADK is leaner and natively aligned with Gemini.
- OpenAI function calling: Would require a separate API key and billing; ADK keeps the primary stack on Google AI Studio.
- Ollama direct REST API: LiteLlm with `ollama_chat/` provides unified ADK tool calling without custom protocol handlers or loop hazards.

## R2: Historical Data Storage

**Decision**: DuckDB with Kaggle CSV ingestion, `\N` → NULL normalization, read-only SQL views

**Rationale**: DuckDB is an embedded analytical database that requires zero infrastructure (no server process). It excels at analytical queries over CSV-scale data (~100K–1M rows). The `\N` sentinel used in Ergast/Kaggle CSVs must be normalized to SQL NULL at ingestion time to prevent silent type errors. Read-only views (`v_race_results`, `v_qualifying`, `v_pit_stops`, `v_driver_standings`) provide a stable query interface and prevent accidental writes — enforcing Constitution Principle I (all numbers from SQL).

**Alternatives Considered**:
- SQLite: Lacks analytical query optimizations (columnar scans, vectorized execution) that DuckDB provides.
- PostgreSQL: Requires a running server process; overkill for 5–10 concurrent users with static historical data.
- Pandas-only: No SQL interface for the LLM to generate queries against; would require the LLM to write Python data manipulation code instead, increasing hallucination surface.

**Key Implementation Details**:
- Ingestion script reads all CSVs from `data/kaggle_csvs/`, replaces `\N` strings with NULL during COPY.
- Views are created at startup via `CREATE OR REPLACE VIEW` statements.
- DuckDB connection is opened in read-only mode for query execution tools; write access only during initial ingestion.

## R3: Car Telemetry Pipeline

**Decision**: FastF1 with persistent disk cache (`./data/fastf1_cache`) + NumPy 1-meter distance interpolation

**Rationale**: FastF1 is the de-facto Python library for accessing F1 telemetry data (2018+). Its built-in caching avoids re-downloading large session files. NumPy 1-meter distance interpolation resamples telemetry channels to a uniform spatial grid, which is essential for accurate corner slicing (±200m entry-apex-exit windows) and driver-to-driver comparison — you can't compare two drivers' speed at "the same point on track" without spatial alignment.

**Alternatives Considered**:
- Raw F1 timing API: No public stable API; FastF1 abstracts this.
- Time-based interpolation: Would misalign traces through corners where drivers have different speeds (and thus cover distance at different rates). Distance-based is correct for spatial comparisons.

**Key Implementation Details**:
- `fastf1.Cache.enable_cache('./data/fastf1_cache')` at app startup.
- Cache-first fallback: check cache before network call; on transient timeout, retry 1–2 times; fail with error if uncached.
- Interpolation: `np.interp()` to resample Speed, Throttle, Brake, Gear, RPM, DRS onto a 1-meter distance grid per lap.

## R4: Corner Identification & Slicing

**Decision**: Curated `data/corner_nicknames.json` + fuzzy entity resolver

**Rationale**: Corner nicknames (Eau Rouge, Copse, 130R, Parabolica, Maggotts-Becketts) are culturally significant but have no programmatic standard. A curated JSON mapping provides deterministic, auditable corner-to-turn-number resolution. The fuzzy resolver handles spelling variations and partial matches. The ±200m entry-apex-exit slicing window is defined per corner based on the JSON metadata.

**JSON Structure**:
```json
{
  "silverstone": {
    "circuit_key": "silverstone",
    "corners": {
      "copse": { "turn_number": 9, "distance_m": 2340 },
      "maggotts": { "turn_number": 11, "distance_m": 2890 },
      "becketts": { "turn_number": 12, "distance_m": 3050 },
      "stowe": { "turn_number": 15, "distance_m": 4200 }
    }
  },
  "spa": {
    "circuit_key": "spa",
    "corners": {
      "eau_rouge": { "turn_number": 3, "distance_m": 850 },
      "raidillon": { "turn_number": 4, "distance_m": 1020 }
    }
  }
}
```

**Alternatives Considered**:
- Automatic corner detection from curvature: Unreliable for complex corner sequences (Maggotts-Becketts) and requires GPS coordinate processing per circuit.
- Hardcoded turn numbers in source: Not maintainable or auditable; JSON is easier to extend.

## R5: Visualization Strategy

**Decision**: Plotly JSON builders (backend) + react-plotly.js (frontend), two-tier system

**Rationale**: Plotly's JSON-serializable figure format allows the backend to construct complete chart specifications (including the dark HUD theme, team colors, axis labels) and send them to the frontend as JSON over SSE. react-plotly.js renders them interactively with zero additional chart logic on the client. The two-tier system:
- **Tier 1 (Preset charts)**: Backend Python functions build Plotly JSON for known chart types (corner comparison, full-lap overlay, stint degradation, position evolution, historical bar/line/table). These are deterministic and testable.
- **Tier 2 (Ad-hoc charts)**: The LLM generates Python code that uses Plotly to build a figure; this code runs in the timeout-guarded sandbox. The sandbox has access to DuckDB query results and NumPy but no filesystem or network.

**Alternatives Considered**:
- D3.js: Maximum flexibility but requires significant frontend charting code; Plotly provides interactive charts with minimal client code.
- Chart.js: Lacks the multi-subplot support needed for synchronized telemetry panels (Speed + Throttle + Brake + Gear).
- Matplotlib: Server-side rasterization produces static images, not interactive charts.

## R6: Streaming Architecture

**Decision**: FastAPI SSE via `/api/chat/stream` endpoint

**Rationale**: Server-Sent Events (SSE) provide a simple, HTTP-native streaming mechanism that works with standard browser `EventSource` API. Each SSE event carries a typed payload: `status` (progress messages), `text` (LLM commentary), `chart` (Plotly JSON), `trace` (Engineering Trace data), `error`. This maps cleanly to the streaming progress requirement (FR-012) and allows the frontend to render incremental results.

**Alternatives Considered**:
- WebSockets: Bidirectional, but the client only needs to send one message (the question); SSE is simpler for server-push patterns.
- Long polling: Higher latency and more complex client logic.
- gRPC streaming: Would require a gRPC client in the browser (gRPC-web), adding complexity.

## R7: Authentication

**Decision**: Session-based authentication with sign-in required

**Rationale**: The app requires authentication (FR-022) for all features. For 5–10 concurrent users, a simple session-based auth with JWT tokens is sufficient. OAuth integration can be added later. Sessions are stateless across browser sessions (FR-024) — conversation context is not persisted.

## R8: Ad-Hoc Python Sandbox

**Decision**: Timeout-guarded restricted `exec()` with controlled globals

**Rationale**: FR-011 requires safe execution of LLM-generated Python. The sandbox provides a restricted `exec()` environment with:
- Allowed imports: `numpy`, `pandas`, `plotly`, `math`, `statistics`, `datetime`
- No filesystem access (`open`, `os`, `pathlib` blocked)
- No network access (`requests`, `urllib`, `socket` blocked)
- No subprocess/system calls
- Execution timeout (configurable, default 30s)
- Pre-injected variables: query results (DataFrames), DuckDB connection (read-only)

**Alternatives Considered**:
- Docker container per execution: Secure but adds 2–5s container startup latency; overkill for 5–10 users.
- WebAssembly sandbox (Pyodide): Would require shipping Python runtime to the browser; unnecessary when backend can sandbox.
- Restricted AST analysis: Too brittle; timeout + controlled globals is simpler and more robust.

## R9: Entity Resolution

**Decision**: Fuzzy driver/circuit resolver using string similarity matching

**Rationale**: Users type driver names and circuit names in natural language with varying specificity ("Max", "Verstappen", "Max Verstappen", "VER"). A fuzzy resolver uses string similarity (Levenshtein distance or token-based matching) to map user input to canonical driver codes and circuit identifiers in the DuckDB database. This bridges the gap between natural language and the structured data model.

**Key Implementation Details**:
- Driver resolver: matches against full name, surname, and 3-letter code from DuckDB `drivers` table.
- Circuit resolver: matches against circuit name, location, and country.
- Corner resolver: matches against `corner_nicknames.json` entries.
- Confidence threshold: matches below a configurable similarity score trigger a disambiguation prompt.

## R10: Frontend Architecture

**Decision**: React + TypeScript + Vite + Tailwind CSS + react-plotly.js

**Rationale**: React provides component-based UI composition. TypeScript adds type safety for the SSE event contracts. Vite offers fast HMR during development. Tailwind CSS enables the dark pit-wall aesthetic with utility classes. react-plotly.js renders Plotly JSON figures with built-in interactivity (hover, zoom, pan). The layout is a two-panel design: chat + preset prompts on the left, interactive Plotly stage + collapsible Engineering Trace drawer on the right.

**Dark HUD Theme**:
- Background: `#0B0F17` (Tailwind custom color `pitwall-bg`)
- Text: `#E2E8F0` (slate-200, 12.6:1 contrast ratio vs #0B0F17)
- Muted: `#64748B` (slate-500, for grid lines and secondary chrome)
- Accent: Team colors from FastF1 at runtime
