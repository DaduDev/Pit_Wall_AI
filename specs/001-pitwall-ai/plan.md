# Implementation Plan: PitWall AI — F1 Race Engineer

**Branch**: `001-pitwall-ai` | **Date**: 2026-11-22 | **Spec**: [spec.md](file:///D:/Learning/F1_Tracker/f1-race-engineer/specs/001-pitwall-ai/spec.md)

**Input**: Feature specification from `/specs/001-pitwall-ai/spec.md`

## Summary

Build PitWall AI, a web application that answers natural-language Formula 1 questions (1950–2024+) with interactive Plotly visualizations. The backend uses Python 3.12+ with FastAPI (SSE streaming), Google ADK with Gemini 3.5 Flash Lite (primary) and local Ollama fallback for LLM orchestration and tool routing, DuckDB for historical race data, and FastF1 with NumPy for car telemetry (2018+). The frontend is a React + TypeScript + Vite + Tailwind CSS application with a dark pit-wall layout and react-plotly.js charts. Every user-facing number is computed via deterministic SQL or Python — never from LLM memory (zero-hallucination guarantee per Constitution Principle I).

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x (frontend)

**Primary Dependencies**:
- Backend: FastAPI, google-adk (Google ADK), duckdb, fastf1, numpy, plotly, litellm (for Ollama fallback)
- Frontend: React 18+, Vite, Tailwind CSS, react-plotly.js
- Testing: pytest, playwright

**LLM Orchestration & Fallback**:
- **Primary LLM**: Configured purely via `.env` / environment (`GEMINI_API_KEY` or `GOOGLE_API_KEY`, `GEMINI_MODEL`, and optional Vertex AI vars `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`) through a unified `backend/app/llm/` client helper shared across `PitWallEngineer`, `HistoricalSQLAgent`, and `ResearchAgent`. Simple SQL generation and radio narration disable or minimize thinking (`thinking_budget=0` for Gemini 2.5 Flash models, or lowest supported `thinking_level` guarded safely per model).
- **4-Tier Cascading Failover LLM Chain**: Independent 60s `429` circuit breakers per cloud provider (`gemini`, `groq`, `openrouter`) and environment-gated local Ollama fallback:
  1. Gemini (primary via `GEMINI_API_KEY` / Vertex AI).
  2. Groq OpenAI-compatible chat completions (`GROQ_BASE_URL`, `GROQ_MODEL=openai/gpt-oss-120b`, `timeout=30.0`, trimmed context for 8K TPM budget) -> `provider="groq_fallback"`.
  3. OpenRouter OpenAI-compatible chat completions (`OPENROUTER_BASE_URL`, `OPENROUTER_MODEL=openrouter/free`, `timeout=35.0`, optional `HTTP-Referer` & `X-Title: PitWall AI` headers) -> `provider="openrouter_fallback"`.
  4. Local Ollama over IPv4 (`OLLAMA_BASE_URL`, `OLLAMA_MODEL=qwen3.5:4b`, `"think": false`, `"keep_alive": "15m"`, `"options": {"num_ctx": 1024, "num_predict": 180, "temperature": 0.3}`, `150s` Ollama / `180s` A2A timeout) gated by `ENABLE_OLLAMA_FALLBACK` (`True` when `APP_ENV != "production"`, `False` when `APP_ENV == "production"`) -> `provider="ollama_fallback"`.
  All provider errors are logged via `logger.warning` without leaking raw 429 JSON into UI text; SSE `trace` events and React HUD (`WebIntelligenceCard` & `TraceDrawer`) display accurate provider labels (`gemini`, `cache`, `groq_fallback`, `openrouter_fallback`, `ollama_fallback`).
- **Research Grounding Cache**: `./data/research_cache/` stores grounded web intelligence payloads so repeat queries spend 0 API quota.
- **Concurrency & Quota Protection**: Gemini requests are governed by an `asyncio.Semaphore(3)` + brief exponential backoff. ADK tools are designed coarse-grained (target <=2 LLM calls per question). Includes an in-memory/SQLite response cache for repeated and preset prompts.

**Storage**: DuckDB (file-based, ingesting Kaggle CSVs with `\N` → NULL normalization). FastF1 persistent disk cache at `./data/fastf1_cache`.

**Testing**: pytest (backend unit/integration), Playwright (frontend E2E smoke tests)

**Target Platform**: Web application (desktop-primary), served via FastAPI backend + Vite-built SPA frontend

**Project Type**: Web application (Python API backend + React SPA frontend)

**Performance Goals**: SQL queries < 5s, telemetry comparisons < 15s end-to-end, streaming progress for any operation > 2s

**Constraints**: 5–10 concurrent authenticated users, sandbox-restricted ad-hoc Python execution (no FS, no network, timeout-guarded), cache-first FastF1 fallback with 1–2 retries

**Scale/Scope**: Single-instance deployment, ~75 years of historical data (~25 CSV tables), telemetry for 2018+ seasons

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Zero-Hallucination Math | ✅ PASS | LLM (Gemini via ADK) authors SQL/Python tools; DuckDB executes SQL, NumPy computes telemetry. No LLM arithmetic. |
| II | Data Domain Separation | ✅ PASS | DuckDB for historical (1950–2024+), FastF1 for telemetry (2018+). Separate tool functions, explicit domain labels in responses. |
| III | Telemetry HUD Visual Standards | ✅ PASS | Dark HUD #0B0F17 background via Plotly layout template + Tailwind dark theme. WCAG AA contrast enforced. |
| IV | Provenance Transparency | ✅ PASS | Engineering Trace panel (collapsible drawer) shows exact SQL query or FastF1 session/lap/driver params for every response. |
| V | Automated Verification | ✅ PASS | pytest suites with real data fixtures (Kaggle CSVs, cached 2024 British GP Qualifying). Playwright E2E smoke tests. |
| VI | Official F1 Team Colors | ✅ PASS | Colors sourced from `fastf1.plotting.get_team_color()` at runtime, season-aware. Contrast-checked against #0B0F17. |
| VII | Session & Lap Metadata Fidelity | ✅ PASS | Every visualization includes GP name, year, session type, lap number, driver code, compound, weather — sourced from data payload. |

**Gate Result**: ✅ ALL PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-pitwall-ai/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-contracts.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                    # FastAPI app + CORS + lifespan (DuckDB init)
│   ├── config.py                  # Settings (paths, model name, timeouts)
│   ├── auth/
│   │   ├── router.py              # /api/auth/* endpoints
│   │   └── dependencies.py        # Auth dependency (JWT/session validation)
│   ├── chat/
│   │   ├── router.py              # POST /api/chat/stream (SSE endpoint)
│   │   ├── session.py             # Conversation session context (rolling summary + recent turns)
│   │   └── streaming.py           # SSE event formatters
│   ├── agent/
│   │   ├── orchestrator.py        # Google ADK agent definition (Gemini 3.5 Flash Lite + Ollama fallback)
│   │   ├── tools/
│   │   │   ├── historical_sql.py  # DuckDB SQL generation + execution tool
│   │   │   ├── telemetry.py       # FastF1 telemetry loading + processing tool
│   │   │   ├── corner_compare.py  # Corner-by-corner slicing + metrics tool
│   │   │   ├── strategy.py        # Stint degradation, position evolution tool
│   │   │   ├── prediction.py      # Winner prediction tool
│   │   │   └── adhoc_sandbox.py   # Sandboxed Python execution tool (Tier 2)
│   │   └── prompts/
│   │       └── system.py          # System prompt with tool routing instructions
│   ├── data/
│   │   ├── duckdb_manager.py      # DuckDB connection, CSV ingestion, \N→NULL
│   │   ├── views.py               # Read-only SQL views (v_race_results, v_qualifying, etc.)
│   │   ├── fastf1_cache.py        # FastF1 cache manager (disk cache + retry logic)
│   │   └── entity_resolver.py     # Fuzzy driver/circuit name resolver
│   ├── charts/
│   │   ├── plotly_theme.py        # Dark HUD Plotly template (#0B0F17, team colors)
│   │   ├── telemetry_charts.py    # Corner comparison + full-lap overlay builders
│   │   ├── strategy_charts.py     # Stint degradation + position evolution builders
│   │   └── historical_charts.py   # Bar, line, table chart builders for SQL results
│   └── sandbox/
│       └── executor.py            # Timeout-guarded restricted Python exec for ad-hoc
├── data/
│   ├── kaggle_csvs/               # Raw CSV files (races.csv, results.csv, etc.)
│   ├── f1_data.duckdb             # DuckDB database file
│   ├── fastf1_cache/              # FastF1 persistent disk cache
│   └── corner_nicknames.json      # Curated corner nickname → turn number mapping
├── tests/
│   ├── conftest.py                # Shared fixtures (DuckDB test instance, cached session)
│   ├── test_duckdb_ingestion.py   # \N normalization, view correctness
│   ├── test_sql_guardrails.py     # Read-only enforcement, injection prevention
│   ├── test_corner_slicing.py     # Corner math on 2024 British GP Qualifying fixture
│   ├── test_entity_resolver.py    # Fuzzy matching accuracy
│   ├── test_telemetry_tools.py    # FastF1 loading, interpolation, metrics
│   ├── test_chart_builders.py     # Plotly JSON structure validation
│   └── test_prediction.py         # Prediction factor traceability
├── requirements.txt
└── pyproject.toml

frontend/
├── src/
│   ├── main.tsx                        # React entry point
│   ├── App.tsx                         # Single-column conversational HUD shell, slim header (+ New Session), centered feed & floating composer
│   ├── components/
│   │   ├── ChatPanel/
│   │   │   ├── WelcomeHero.tsx         # Empty-state hero + 2x2 starter prompt cards
│   │   │   ├── TurnItem.tsx            # Per-turn feed item (Status -> Visual Artifact -> Prose -> Collapsible Trace)
│   │   │   ├── MessageBubble.tsx       # User bubble & Race Engineer markdown commentary
│   │   │   ├── ComposerBar.tsx         # Floating bottom dark pill composer (Prompts popover, textarea, mic slot, Send)
│   │   │   ├── PresetPrompts.tsx       # Categorized quick-prompt popover menu
│   │   │   └── StreamingStatus.tsx     # Live per-turn SSE progress pill
│   │   ├── ChartStage/
│   │   │   ├── ChartStage.tsx          # Inline turn visual renderer (Plotly, KpiCard, DataTableCard, WebIntelligenceCard, fullscreen modal)
│   │   │   ├── PlotlyChart.tsx         # Responsive Plotly wrapper (`useResizeHandler={true}`, dark `#0B0F17`)
│   │   │   ├── TrackMiniMap.tsx        # GPS track mini-map for corner comparisons
│   │   │   ├── SectorSummaryBar.tsx    # Full-lap sector & speed-trap splits
│   │   │   ├── KpiCard.tsx             # Single-row HUD KPI card
│   │   │   ├── DataTableCard.tsx       # Multi-row HUD classification table
│   │   │   └── WebIntelligenceCard.tsx # Research grounding / fallback summary card
│   │   ├── EngineeringTrace/
│   │   │   └── TraceDrawer.tsx         # Compact single-line toggle expanding full provenance & A2A hops
│   │   ├── MetadataBar/
│   │   │   └── MetadataBar.tsx         # Session/lap/driver badges strip
│   │   └── Auth/
│   │       └── LoginPage.tsx           # Authentication gate
│   ├── hooks/
│   │   ├── useSSEStream.ts             # SSE connection binding per-turn chart/minimap/trace payloads
│   │   └── useAuth.ts                  # Authentication state management
│   ├── services/
│   │   └── api.ts                      # API client (auth, chat endpoints)
│   ├── types/
│   │   └── index.ts                    # Shared TypeScript interfaces (`ChatMessage` with inline `chart`/`minimap`/`trace`/`status`)
│   └── styles/
│       └── globals.css                 # Tailwind base + dark HUD custom properties
├── tests/
│   └── smoke.spec.ts              # Playwright: Plotly renders, zero console errors
├── index.html
├── tailwind.config.ts
├── vite.config.ts
├── tsconfig.json
└── package.json
```

**Structure Decision**: Web application with separate `backend/` (Python/FastAPI) and `frontend/` (React/TypeScript/Vite) directories. The backend serves as both the API and the AI orchestration layer. The frontend is a Vite-built SPA served independently during development and can be bundled for production. This separation cleanly maps to the two-domain architecture (DuckDB historical + FastF1 telemetry on the backend, Plotly rendering on the frontend).

## Complexity Tracking

> No constitution violations detected — no complexity justifications needed.
