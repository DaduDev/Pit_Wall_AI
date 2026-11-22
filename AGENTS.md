# PitWall AI — Agent Context & Rules

## Project Overview
**PitWall AI** is an AI Race Engineer web application that answers natural-language Formula 1 questions spanning 1950 to 2024+ with interactive Plotly visualizations.

- **Active Feature**: `001-pitwall-ai` ([specs/001-pitwall-ai/spec.md](specs/001-pitwall-ai/spec.md))
- **Implementation Plan**: [specs/001-pitwall-ai/plan.md](specs/001-pitwall-ai/plan.md)
- **Constitution**: [.specify/memory/constitution.md](.specify/memory/constitution.md)

---

## Non-Negotiable Constitution Principles

1. **Zero-Hallucination Math**:
   - The LLM MUST NEVER calculate statistics, averages, braking points, or lap deltas from memory or parametric weights.
   - Every number displayed to the user MUST originate from DuckDB SQL queries or deterministic Python/NumPy calculations.
2. **Data Domain Separation**:
   - Historical Race Data (1950–2024+): DuckDB SQL views (`v_race_results`, `v_qualifying`, `v_pit_stops`, `v_driver_standings`).
   - Car Telemetry (2018+): FastF1 API with persistent disk cache (`./data/fastf1_cache`) and NumPy 1-meter distance interpolation.
   - Clear boundary explanation MUST be provided if pre-2018 car telemetry is requested.
3. **Telemetry HUD Visual Standards**:
   - All charts, panels, and dashboard canvases MUST use the dark HUD background `#0B0F17`.
   - Text contrast MUST meet WCAG AA (4.5:1 minimum).
4. **Provenance Transparency**:
   - Every result MUST supply Engineering Trace data (exact SQL query or FastF1 session/lap/driver/channel parameters).
5. **Automated Verification**:
   - All features MUST be backed by pytest suites validating against real race data fixtures (no synthetic mocks for user-facing numbers).
6. **Official F1 Team Colors**:
   - Team colors MUST be retrieved dynamically from `fastf1.plotting.get_team_color()` for the specific season, never hardcoded.
7. **Session & Lap Metadata Fidelity**:
   - Grand Prix name, season year, session type, lap number, driver code, compound, and weather MUST be shown on all visualizations.

---

## Technical Stack & Architecture

### Backend (`backend/`)
- **Runtime**: Python 3.12+
- **Framework**: FastAPI with SSE streaming endpoint at `POST /api/chat/stream`
- **Orchestration**: Google ADK (`google-adk`) using `gemini-3.5-flash-lite` (primary via `GOOGLE_API_KEY`, `thinking_level="low"`/`"medium"`, no deprecated parameters) with automatic/manual fallback to local Ollama via `LiteLlm(model="ollama_chat/qwen3.5:4b")`, `asyncio.Semaphore(3)` quota guard, and response caching
- **Historical Data**: DuckDB (`data/f1_data.duckdb`) ingesting Kaggle CSVs (`data/kaggle_csvs/`) with `\N` → `NULL` normalization and curated read-only views
- **Car Telemetry**: FastF1 with disk cache at `./data/fastf1_cache` + NumPy 1-meter spatial interpolation for corner slicing (±200m around corner reference points)
- **Entity Resolution**: Fuzzy driver/circuit name matching + `data/corner_nicknames.json`
- **Visualizations**: Plotly JSON builders (Tier 1 preset figures + Tier 2 restricted Python sandbox for ad-hoc queries)
- **Authentication**: JWT session tokens; users must sign in; stateless across browser sessions (last 4–6 turns verbatim + rolling summary within a session)

### Frontend (`frontend/`)
- **Framework**: React 18+ with TypeScript and Vite
- **Styling**: Tailwind CSS configured with `#0B0F17` HUD background (`pitwall-bg`)
- **Charts**: `react-plotly.js` rendering backend-supplied Plotly figures
- **Layout**: Two-panel dark pit-wall interface (chat + preset prompts left; interactive Plotly stage + collapsible Engineering Trace drawer right)

### Testing
- **Backend**: `pytest` covering DuckDB `\N` ingestion, read-only SQL guardrails, corner-slicing math (2024 British GP Qualifying fixture), and prediction factor traceability
- **Frontend**: Playwright E2E smoke test verifying Plotly rendering and zero console errors

---

## Artifact Index (Feature `001-pitwall-ai`)

- **Feature Spec**: [`specs/001-pitwall-ai/spec.md`](specs/001-pitwall-ai/spec.md)
- **Implementation Plan**: [`specs/001-pitwall-ai/plan.md`](specs/001-pitwall-ai/plan.md)
- **Research & Decisions**: [`specs/001-pitwall-ai/research.md`](specs/001-pitwall-ai/research.md)
- **Data Model**: [`specs/001-pitwall-ai/data-model.md`](specs/001-pitwall-ai/data-model.md)
- **API Contracts**: [`specs/001-pitwall-ai/contracts/api-contracts.md`](specs/001-pitwall-ai/contracts/api-contracts.md)
- **Quickstart Guide**: [`specs/001-pitwall-ai/quickstart.md`](specs/001-pitwall-ai/quickstart.md)
- **Spec Quality Checklist**: [`specs/001-pitwall-ai/checklists/requirements.md`](specs/001-pitwall-ai/checklists/requirements.md)
