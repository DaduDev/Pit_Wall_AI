# Tasks: PitWall AI — F1 Race Engineer

**Input**: Design documents from `/specs/001-pitwall-ai/` ([spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [research.md](research.md), [contracts/api-contracts.md](contracts/api-contracts.md), [quickstart.md](quickstart.md))

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md), [contracts/api-contracts.md](contracts/api-contracts.md), [constitution.md](../../.specify/memory/constitution.md)

**Tests**: Automated pytest and Playwright tests are mandatory per Constitution Principle V and the feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2...); omitted for Setup, Foundational, and Polish phases
- Every task includes explicit target file paths and resolving citations to `data-model.md` entities/fields where constrained data is handled

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, environment setup, and dependency configuration across backend and frontend

- [X] T001 Initialize backend Python 3.12 project structure, virtual environment, and dependency manifest in `backend/requirements.txt` and `backend/pyproject.toml`
- [X] T002 [P] Initialize frontend React + TypeScript + Vite project with Tailwind CSS and dependencies in `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, and `frontend/tailwind.config.ts`
- [X] T003 [P] Configure backend test harness and shared pytest fixtures in `backend/tests/conftest.py`
- [X] T004 [P] Configure frontend Playwright test configuration in `frontend/playwright.config.ts`
- [X] T005 [P] Create application configuration module managing environment variables, FastF1 cache path, DuckDB file path, and Gemini API keys in `backend/app/config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data ingestion, authentication, routing, and shared UI shell that MUST be complete before ANY user story can begin

**⚠️ CRITICAL**: No user story work can begin until this foundational phase is complete.

- [X] T006 Implement DuckDB manager with Kaggle CSV ingestion logic converting `\N` sentinels to `NULL` for all tables in `backend/app/data/duckdb_manager.py` (cites `data-model.md`: `circuits.circuitId`, `circuits.name`, `constructors.constructorId`, `constructors.name`, `drivers.driverId`, `drivers.forename`, `races.raceId`, `races.round`, `races.name`, `races.date`, `results.resultId`, `results.points`, `results.laps`, `qualifying.qualifyId`, `lap_times.raceId`, `pit_stops.raceId`, `driver_standings.driverStandingsId`, `constructor_standings.constructorStandingsId`, `status.statusId`)
- [X] T007 [P] Create curated read-only DuckDB SQL views (`v_race_results`, `v_qualifying`, `v_pit_stops`, `v_driver_standings`, `v_constructor_standings`) in `backend/app/data/views.py` (cites `data-model.md`: `v_race_results`, `v_qualifying`, `v_pit_stops`, `v_driver_standings`, `v_constructor_standings`)
- [X] T008 [P] Implement read-only SQL guardrail validator rejecting all mutating statements (INSERT, UPDATE, DELETE, DROP, ALTER) in `backend/app/data/duckdb_manager.py`
- [X] T009 [P] Initialize FastF1 disk cache manager with cache-first fallback and retry helper in `backend/app/data/fastf1_cache.py` (cites `data-model.md`: FastF1 cache `./data/fastf1_cache`)
- [X] T010 [P] Implement curated corner nickname mapping loader in `backend/app/data/entity_resolver.py` parsing `backend/data/corner_nicknames.json` (cites `data-model.md`: `Corner.turn_number`, `Corner.distance_m`, `Corner.nickname`, `Corner.circuit_key`)
- [X] T011 Implement fuzzy driver and circuit entity resolver matching name variants to canonical driver codes and circuit IDs in `backend/app/data/entity_resolver.py` (cites `data-model.md`: `drivers.code`, `drivers.surname`, `circuits.circuitRef`)
- [X] T012 Implement JWT authentication service, password hashing, and user dependencies in `backend/app/auth/dependencies.py` and router in `backend/app/auth/router.py` (cites `data-model.md`: `UserAccount.user_id`, `UserAccount.email`, `UserAccount.password_hash`, contracts: `POST /api/auth/login`, `POST /api/auth/register`)
- [X] T013 [P] Implement in-memory conversation session context manager with rolling summary + last 4–6 verbatim turns in `backend/app/chat/session.py` (cites `data-model.md`: `ConversationSession.session_id`, `ConversationSession.rolling_summary`, `ConversationSession.recent_turns`)
- [X] T014 [P] Implement SSE event formatting helpers (`session`, `status`, `text`, `chart`, `trace`, `error`, `done`) in `backend/app/chat/streaming.py` (cites `contracts/api-contracts.md`: SSE Event Type Summary)
- [X] T015 Implement dark HUD Plotly template with base `#0B0F17` background and WCAG AA contrast styling in `backend/app/charts/plotly_theme.py`
- [X] T016 Setup FastAPI application with CORS, exception handlers, health endpoint `GET /api/health`, and authentication middleware in `backend/app/main.py` (cites `contracts/api-contracts.md`: `GET /api/health`)

**Checkpoint**: Foundation ready — database loaded, auth working, FastF1 cache configured, streaming foundation ready. User story implementation can now begin.

---

## Phase 3: User Story 1 - Historical F1 Question Answering (Priority: P1) 🎯 MVP

**Goal**: Enable users to ask natural-language questions about 1950–2024+ F1 history and receive answers grounded in DuckDB SQL queries with interactive Plotly charts/tables and an Engineering Trace.

**Independent Test**: Query "Who won the 2023 Bahrain Grand Prix?" and "Show me Lewis Hamilton's podium finishes per season"; verify results against FIA records with 100% mathematical fidelity and inspect exact DuckDB SQL in Engineering Trace.

### Tests for User Story 1

- [X] T017 [P] [US1] Create pytest suite for DuckDB ingestion and `\N` to `NULL` normalization in `backend/tests/test_duckdb_ingestion.py`
- [X] T018 [P] [US1] Create pytest suite for read-only SQL guardrails and injection rejection in `backend/tests/test_sql_guardrails.py`
- [X] T019 [P] [US1] Create integration test for historical query tool execution in `backend/tests/test_historical_tool.py`

### Implementation for User Story 1

- [X] T020 [P] [US1] Implement DuckDB historical SQL query execution tool with timeout and read-only enforcement in `backend/app/agent/tools/historical_sql.py` (cites `data-model.md`: `races.year`, `results.position`, `v_race_results`, `v_driver_standings`)
- [X] T021 [P] [US1] Implement historical chart builders for bar, line, and classification tables with `#0B0F17` theme in `backend/app/charts/historical_charts.py`
- [X] T022 [US1] Implement Google ADK orchestrator agent in `backend/app/agent/orchestrator.py` and `backend/app/agent/prompts/system.py`: configure primary `gemini-3.5-flash-lite` (`thinking_level="low"`/`"medium"`, no deprecated parameters), local Ollama fallback via `LiteLlm(model="ollama_chat/qwen3.5:4b")` with context trimmed to last 2 turns, `asyncio.Semaphore(3)` concurrency guard, and response caching for repeated/preset prompts
- [X] T023 [US1] Connect SSE streaming chat endpoint `POST /api/chat/stream` for historical Q&A in `backend/app/chat/router.py` (cites `contracts/api-contracts.md`: `POST /api/chat/stream`)
- [X] T024 [P] [US1] Implement frontend authentication page and login hook in `frontend/src/components/Auth/LoginPage.tsx` and `frontend/src/hooks/useAuth.ts`
- [X] T025 [P] [US1] Implement dark HUD layout shell with left chat panel and right chart stage in `frontend/src/App.tsx`, `frontend/src/styles/globals.css`, and `frontend/src/types/index.ts`
- [X] T026 [US1] Implement chat UI with message list and streaming status indicator in `frontend/src/components/ChatPanel/ChatPanel.tsx`, `frontend/src/components/ChatPanel/MessageBubble.tsx`, and `frontend/src/hooks/useSSEStream.ts`
- [X] T027 [US1] Implement interactive Plotly stage and collapsible Engineering Trace drawer in `frontend/src/components/ChartStage/ChartStage.tsx`, `frontend/src/components/ChartStage/PlotlyChart.tsx`, and `frontend/src/components/EngineeringTrace/TraceDrawer.tsx`

**Checkpoint**: User Story 1 is fully functional as an MVP. Users can sign in, submit historical queries, see interactive charts, and inspect SQL traces.

---

## Phase 4: User Story 2 - Corner-by-Corner Telemetry Comparison (Priority: P1)

**Goal**: Compare two drivers through a specific corner (by turn number or nickname like Copse/Eau Rouge) with synchronized multi-panel telemetry (Speed, Delta, Throttle, Brake, Gear), zoomed GPS mini-map, and grounded race-engineer commentary.

**Independent Test**: Submit "Compare Verstappen and Leclerc through Copse at the 2024 British GP Qualifying" and verify braking point delta, apex min speed, lowest gear, full-throttle pickup, and corner time delta against FastF1 calculations.

### Tests for User Story 2

- [X] T028 [P] [US2] Create unit test suite for fuzzy entity resolver (drivers, circuits, corner nicknames) in `backend/tests/test_entity_resolver.py`
- [X] T029 [P] [US2] Create integration test suite for 1-meter interpolation and ±200m corner slicing math using cached 2024 British GP Qualifying fixture in `backend/tests/test_corner_slicing.py`

### Implementation for User Story 2

- [X] T030 [P] [US2] Implement telemetry data loader with 1-meter spatial distance interpolation using `scipy`/`numpy` in `backend/app/agent/tools/telemetry.py` (cites `data-model.md`: `TelemetryLap.Distance`, `TelemetryLap.Speed`, `TelemetryLap.Throttle`, `TelemetryLap.Brake`, `TelemetryLap.nGear`, `TelemetryLap.RPM`, `TelemetryLap.DRS`, `TelemetryLap.X`, `TelemetryLap.Y`, `TelemetryLap.Z`)
- [X] T031 [P] [US2] Implement dynamic team color resolver querying `fastf1.plotting.get_team_color()` for season with contrast validation against `#0B0F17` in `backend/app/charts/plotly_theme.py` (cites `data-model.md`: `SessionMetadata.team_color`)
- [X] T032 [US2] Implement corner slicing tool calculating the 5 corner metrics (braking point delta, apex min speed, lowest gear, full-throttle pickup, corner time delta) across ±200m in `backend/app/agent/tools/corner_compare.py` (cites `data-model.md`: Computed Corner Metrics)
- [X] T033 [US2] Implement multi-panel synchronized Plotly chart builder (Speed, Delta, Throttle, Brake, Gear) and GPS track coordinate builder in `backend/app/charts/telemetry_charts.py`
- [X] T034 [P] [US2] Implement session and lap metadata extraction (GP name, year, session type, lap number, driver code, compound, weather) in `backend/app/agent/tools/telemetry.py` (cites `data-model.md`: `SessionMetadata.event_name`, `SessionMetadata.year`, `SessionMetadata.session_type`, `SessionMetadata.driver_code`, `SessionMetadata.compound`)
- [X] T035 [US2] Register corner comparison tool in Google ADK agent with race-engineer commentary prompt grounded in computed metrics in `backend/app/agent/orchestrator.py` and `backend/app/agent/prompts/system.py`
- [X] T036 [US2] Connect corner comparison tool execution and trace payload emission in `backend/app/chat/router.py` (cites `contracts/api-contracts.md`: `event: trace` with `telemetry_params`)
- [X] T037 [P] [US2] Implement session metadata bar component in `frontend/src/components/MetadataBar/MetadataBar.tsx`
- [X] T038 [P] [US2] Implement zoomed GPS track mini-map component colored by faster driver in `frontend/src/components/ChartStage/TrackMiniMap.tsx`
- [X] T039 [US2] Enhance frontend Plotly chart stage to support synchronized multi-panel telemetry charts and tooltips in `frontend/src/components/ChartStage/PlotlyChart.tsx`
- [X] T040 [US2] Add preset prompts for famous corners (Copse, Eau Rouge, 130R) in `frontend/src/components/ChatPanel/PresetPrompts.tsx`

**Checkpoint**: User Stories 1 and 2 both work independently. Users can seamlessly transition from historical statistics to deep corner-by-corner telemetry analysis.

---

## Phase 5: User Story 3 - Full-Lap Telemetry Overlay (Priority: P2)

**Goal**: Overlay two drivers' full-lap telemetry traces across an entire lap with official team colors, delta trace, and sector splits.

**Independent Test**: Request "Overlay Verstappen vs Hamilton full lap at 2023 Abu Dhabi Qualifying" and confirm speed trace matches FastF1 lap data across 100% of lap distance.

### Tests for User Story 3

- [X] T041 [P] [US3] Create integration test for full-lap telemetry alignment and speed delta computation in `backend/tests/test_full_lap.py`

### Implementation for User Story 3

- [X] T042 [P] [US3] Implement full-lap telemetry extraction tool in `backend/app/agent/tools/telemetry.py` (cites `data-model.md`: `TelemetryLap.Speed`, `TelemetryLap.Distance`, `SessionMetadata.lap_time`)
- [X] T043 [US3] Implement full-lap Plotly chart builder with speed overlay, delta trace, and gear application in `backend/app/charts/telemetry_charts.py`
- [X] T044 [US3] Register full-lap overlay tool in Google ADK orchestrator in `backend/app/agent/orchestrator.py`
- [X] T045 [US3] Add missing-lap error handling for drivers without valid timed laps in `backend/app/agent/tools/telemetry.py`
- [X] T046 [US3] Wire full-lap chart and trace event emission through `POST /api/chat/stream` in `backend/app/chat/router.py`
- [X] T047 [P] [US3] Update frontend `frontend/src/components/ChartStage/PlotlyChart.tsx` to handle full-lap multi-channel zoom and pan interactions
- [X] T048 [P] [US3] Add full-lap comparison preset prompts in `frontend/src/components/ChatPanel/PresetPrompts.tsx`

**Checkpoint**: User Story 3 complete and verified independently alongside US1 and US2.

---

## Phase 6: User Story 4 - Tyre Stint Degradation Analysis (Priority: P2)

**Goal**: Analyze tyre degradation per stint during a race, filtering out pit-in/pit-out laps and Safety Car periods, with compound-colored traces and linear degradation trend lines.

**Independent Test**: Request "Show me Verstappen's tyre degradation at the 2023 Spanish GP" and verify pit/Safety Car laps are excluded and degradation rate (sec/lap) matches timing data.

### Tests for User Story 4

- [X] T049 [P] [US4] Create unit test for pit and Safety Car lap filtering in `backend/tests/test_strategy.py`

### Implementation for User Story 4

- [X] T050 [P] [US4] Implement stint extraction and outlier filtering tool in `backend/app/agent/tools/strategy.py` (cites `data-model.md`: `Stint`, `lap_times.lap`, `lap_times.milliseconds`, `SessionMetadata.compound`)
- [X] T051 [US4] Implement linear regression degradation trend line calculation per stint using NumPy in `backend/app/agent/tools/strategy.py`
- [X] T052 [US4] Implement tyre stint degradation Plotly scatter + line chart builder colored by compound in `backend/app/charts/strategy_charts.py`
- [X] T053 [US4] Handle red-flagged races and multi-part stints in `backend/app/agent/tools/strategy.py`
- [X] T054 [US4] Register tyre stint analysis tool in Google ADK agent in `backend/app/agent/orchestrator.py`
- [X] T055 [US4] Wire tyre degradation events through SSE stream in `backend/app/chat/router.py`
- [X] T056 [P] [US4] Add tyre degradation presets and compound legend support in `frontend/src/components/ChatPanel/PresetPrompts.tsx` and `frontend/src/components/ChartStage/PlotlyChart.tsx`

**Checkpoint**: User Story 4 functional; race strategy insights available with clean lap-time filtering.

---

## Phase 7: User Story 5 - Race Position Evolution (Priority: P2)

**Goal**: Render a comprehensive "spaghetti plot" showing lap-by-lap position evolution for all drivers in a Grand Prix, annotated with pit stops, retirements, and Safety Cars.

**Independent Test**: Request "Show me the race position chart for the 2023 Brazilian GP" and verify position lines, pit-stop markers, and DNF statuses against official race classification.

### Tests for User Story 5

- [ ] T057 [P] [US5] Create integration test for race position evolution data extraction in `backend/tests/test_position_evolution.py`

### Implementation for User Story 5

- [ ] T058 [P] [US5] Implement lap-by-lap position extraction tool querying `lap_times` and `pit_stops` in `backend/app/agent/tools/strategy.py` (cites `data-model.md`: `lap_times.position`, `lap_times.lap`, `pit_stops.lap`, `results.positionText`, `status.status`)
- [ ] T059 [US5] Implement position evolution Plotly chart builder with driver line highlights and pit-stop markers in `backend/app/charts/strategy_charts.py`
- [ ] T060 [US5] Register race position evolution tool in Google ADK orchestrator in `backend/app/agent/orchestrator.py`
- [ ] T061 [US5] Wire position evolution chart and trace emissions in `backend/app/chat/router.py`
- [ ] T062 [P] [US5] Implement interactive driver line highlighting on hover/click in `frontend/src/components/ChartStage/PlotlyChart.tsx`
- [ ] T063 [P] [US5] Add race position evolution preset buttons in `frontend/src/components/ChatPanel/PresetPrompts.tsx`
- [ ] T064 [US5] Display event annotations (SC, VSC, Red Flag) on position chart in `frontend/src/components/ChartStage/PlotlyChart.tsx`

**Checkpoint**: User Story 5 functional; full-race position flow visualizable with interactive team-line isolation.

---

## Phase 8: User Story 6 - Ad-Hoc Cross-Metric Analysis (Priority: P3)

**Goal**: Handle custom cross-metric analytical questions not covered by preset charts via a restricted, timeout-guarded Python sandbox returning interactive Plotly figures with explicit computation traces.

**Independent Test**: Submit "Plot average pit stop duration per team across the last 5 seasons" and verify generated Python code executes sandboxed without filesystem/network access and returns a valid Plotly chart.

### Tests for User Story 6

- [ ] T065 [P] [US6] Create unit test suite for Python sandbox security restrictions (blocking `open`, `os`, `socket`, `subprocess`, enforcing timeout) in `backend/tests/test_sandbox.py`

### Implementation for User Story 6

- [ ] T066 [US6] Implement timeout-guarded restricted Python execution sandbox in `backend/app/sandbox/executor.py`
- [ ] T067 [US6] Implement ad-hoc Python execution tool injecting read-only DuckDB connection and Plotly figure exporter in `backend/app/agent/tools/adhoc_sandbox.py`
- [ ] T068 [US6] Configure LLM system prompt instructions for generating safe ad-hoc Python data analysis code in `backend/app/agent/prompts/system.py`
- [ ] T069 [US6] Register ad-hoc sandbox tool in Google ADK agent in `backend/app/agent/orchestrator.py`
- [ ] T070 [US6] Wire ad-hoc Python code into trace event payload in `backend/app/chat/router.py` (cites `contracts/api-contracts.md`: `trace.python_code`)
- [ ] T071 [P] [US6] Render generated Python code in Engineering Trace drawer with copy-to-clipboard affordance in `frontend/src/components/EngineeringTrace/TraceDrawer.tsx`
- [ ] T072 [US6] Handle cross-domain labeling when ad-hoc analysis combines historical SQL and FastF1 telemetry in `backend/app/agent/tools/adhoc_sandbox.py` and `frontend/src/components/EngineeringTrace/TraceDrawer.tsx`

**Checkpoint**: User Story 6 complete; ad-hoc analytics safely supported without opening system-level vulnerabilities.

---

## Phase 9: User Story 7 - Live Progress Streaming & 2018 Boundary Explanation (Priority: P3)

**Goal**: Stream real-time step-by-step tool progress messages to the UI during long computations and gracefully explain the 2018 data boundary when pre-2018 telemetry is requested.

**Independent Test**: Submit "Show me Schumacher's telemetry at the 2004 Italian GP" and verify boundary explanation with historical alternatives; submit a corner comparison and observe progress events streaming before chart displays.

### Tests for User Story 7

- [ ] T073 [P] [US7] Create unit test for 2018 boundary guardrail and explanation generator in `backend/tests/test_boundary_guard.py`

### Implementation for User Story 7

- [ ] T074 [US7] Implement 2018 boundary check intercepting pre-2018 telemetry queries and offering historical SQL alternatives in `backend/app/agent/tools/telemetry.py` (cites `data-model.md`: `Validation Rules: Telemetry Year Boundary`)
- [ ] T075 [US7] Implement granular progress callback hooks across DuckDB queries and FastF1 download stages in `backend/app/chat/streaming.py` and `backend/app/agent/orchestrator.py`
- [ ] T076 [US7] Stream step-by-step progress events over SSE during tool execution in `backend/app/chat/router.py` (cites `contracts/api-contracts.md`: `event: status`)
- [ ] T077 [P] [US7] Implement live progress status drawer/toast in `frontend/src/components/ChatPanel/StreamingStatus.tsx`
- [ ] T078 [US7] Render 2018 boundary explanation with clickable quick-pivot buttons for historical stats in `frontend/src/components/ChatPanel/MessageBubble.tsx`
- [ ] T079 [P] [US7] Implement transient timeout retry indicator in `frontend/src/components/ChatPanel/StreamingStatus.tsx`
- [ ] T080 [US7] Add SSE connection error handling and automatic reconnection logic in `frontend/src/hooks/useSSEStream.ts`

**Checkpoint**: User Story 7 functional; user feedback is responsive and data domain boundaries are clear.

---

## Phase 10: User Story 8 - Winner Prediction (Priority: P3)

**Goal**: Provide grounded race winner and championship predictions based on recent driver/team form, qualifying pace, and circuit history with explicit confidence factors and traceable statistics.

**Independent Test**: Request "Who will win the next race at Silverstone?" and verify prediction output lists ranked candidates, percentage confidence, and every cited stat traces to a DuckDB query in the Engineering Trace.

### Tests for User Story 8

- [ ] T081 [P] [US8] Create unit test for deterministic prediction score calculation and factor traceability in `backend/tests/test_prediction.py`

### Implementation for User Story 8

- [ ] T082 [P] [US8] Implement recent form and circuit history aggregator querying DuckDB in `backend/app/agent/tools/prediction.py` (cites `data-model.md`: `v_race_results`, `v_qualifying`, `races.year`, `circuits.circuitId`)
- [ ] T083 [US8] Implement deterministic weighted ranking algorithm calculating win probabilities and confidence scores in `backend/app/agent/tools/prediction.py`
- [ ] T084 [US8] Implement prediction breakdown Plotly horizontal bar chart showing factor contributions in `backend/app/charts/historical_charts.py`
- [ ] T085 [US8] Register winner prediction tool in Google ADK orchestrator in `backend/app/agent/orchestrator.py`
- [ ] T086 [US8] Wire prediction factor queries into Engineering Trace payload in `backend/app/chat/router.py`
- [ ] T087 [P] [US8] Implement confidence score badges and factor breakdown display in `frontend/src/components/ChatPanel/MessageBubble.tsx`
- [ ] T088 [P] [US8] Add prediction prompt presets for upcoming and historic circuits in `frontend/src/components/ChatPanel/PresetPrompts.tsx`

**Checkpoint**: User Story 8 functional; data-driven predictions available without parametric LLM hallucination.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end integration validation, performance tuning, and Playwright verification

- [ ] T089 [P] Implement end-to-end Playwright smoke test verifying authentication, chat interaction, and Plotly rendering with zero console errors in `frontend/tests/smoke.spec.ts`
- [ ] T090 [P] Validate WCAG AA contrast ratio (4.5:1 minimum) across all chart text and UI elements against `#0B0F17` in `frontend/src/styles/globals.css`
- [ ] T091 Execute full backend pytest suite validating scenarios V1 through V5 and V7 from quickstart guide in `backend/tests/`
- [ ] T092 Verify FastF1 disk cache re-use and offline capability on cached sessions in `backend/app/data/fastf1_cache.py`
- [ ] T093 Conduct concurrency stress test simulating 5–10 concurrent sessions in `backend/tests/test_concurrency.py`
- [ ] T094 [P] Verify responsiveness across desktop and laptop display viewports in `frontend/src/App.tsx`
- [ ] T095 Code cleanup, dead code elimination, and type check verification across backend and frontend
- [ ] T096 Run complete verification workflow per `specs/001-pitwall-ai/quickstart.md`

---

## Phase 12: HUD Visual Cards, SSE `viz_type`, Thinking Latency & Full-Lap Attribution

**Purpose**: Eliminate blank Plotly fallbacks and raw internal text leaks, preserve top-level `viz_type` on SSE `chart` events, trim `HistoricalSQLAgent` / `PitWallEngineer` thinking delay while keeping `.env` model config untouched, and fix full-lap faster-driver attribution.

- [x] T097 Update `PresentationAgent` (`backend/app/a2a/agents/presentation_agent.py`) and `HistoricalSQLAgent` (`backend/app/a2a/agents/historical_agent.py`) so `row_count == 1` returns `{ viz_type: "kpi_card", title: "<clean human title>", kpi_card: { subtitle: "<race/year>", metrics: [{ label, value }] } }`, `row_count >= 2` without sensible numeric y-axis bar chart returns `viz_type: "data_table"`, and zero blank `data: []` Plotly grids or raw `"Retrieved X rows..."` / `"Dataset stored under dataset_id=..."` strings leak into `layout.title` or chat `text`
- [x] T098 Update `backend/app/chat/streaming.py` and `backend/app/agent/orchestrator.py` so every SSE `chart` event preserves top-level `viz_type` (`"corner_telemetry"`, `"full_lap"`, `"tyre_stints"`, `"historical_sql"`, `"kpi_card"`, `"data_table"`, `"web_intelligence_card"`) alongside `figure`, `kpi_card`, `data_table`, or `web_intelligence_card`
- [x] T099 Optimize thinking configuration (`thinking_budget=0` for Gemini 2.5 Flash or lowest supported `thinking_level`, safely guarded) in `HistoricalSQLAgent` and `PitWallEngineer` without altering `.env` `GEMINI_MODEL`
- [x] T100 Update `TelemetryAgent.compare_full_lap` (`backend/app/a2a/agents/telemetry_agent.py`) and `orchestrator.py` to emit explicit `driver_1_lap_time`, `driver_2_lap_time`, and `faster_driver` fields in specialist metrics/summary
- [x] T101 Implement `KpiCard.tsx` and `DataTableCard.tsx` in `frontend/src/components/ChartStage/` (`#0B0F17` HUD) and update `ChartStage.tsx`, `useSSEStream.ts`, and `frontend/src/types/index.ts` to switch cleanly on `viz_type` without mounting empty `<Plot>` instances
- [x] T102 Add regression tests in `backend/tests/` verifying 1-row Brazil 2021 SQL returns `viz_type == "kpi_card"` with zero raw `dataset_id`/`Retrieved 1 rows` text leaks, web research preserves `viz_type == "web_intelligence_card"`, and full-lap summary explicitly names the faster driver
- [x] T103 Run `python -m pytest backend/tests/ -v` and `npm run build` in `frontend/`, recording before/after `HistoricalSQLAgent` latency

---

## Phase 13: Unified Gemini → Local Ollama Failover, Research Cache & Quota Guard

**Purpose**: Eliminate leaked `429 RESOURCE_EXHAUSTED` JSON errors, guarantee automatic Gemini -> local Ollama (`qwen3.5:4b`) failover across `PitWallEngineer`, `HistoricalSQLAgent`, and `ResearchAgent`, add disk caching in `./data/research_cache/`, show accurate provider/fallback badges in React HUD, and protect Gemini quota during `pytest`.

- [x] T104 Create shared `backend/app/llm/` client module supporting env-driven Gemini / Vertex AI (`GEMINI_API_KEY`, `GEMINI_MODEL`, `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`) with automatic Ollama failover (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`), clean server-side `logger.warning`, zero traceback leaks, and `"provider": "gemini" | "ollama_fallback" | "cache"` attribution
- [x] T105 Wire `PitWallEngineer` (`backend/app/agent/orchestrator.py`), `HistoricalSQLAgent` (`backend/app/a2a/agents/historical_agent.py`), and `ResearchAgent` (`backend/app/a2a/agents/research_agent.py`) to use `backend/app/llm/`, stream/emit `"provider"` in SSE `trace` events, and strip empty/whitespace bullets
- [x] T106 Add `./data/research_cache/` persistent disk cache + Ollama offline summarization fallback in `ResearchAgent` in strict priority order (cache -> Gemini Google Search -> Ollama -> clean unreachable message)
- [x] T107 Update `frontend/src/components/ChartStage/WebIntelligenceCard.tsx`, `frontend/src/components/EngineeringTrace/TraceDrawer.tsx`, and `frontend/src/types/index.ts` to render `"Google Search Grounding"` only when `grounded === true`, `"Local Ollama Fallback (Offline Model)"` when `grounded === false`, and `trace.provider` badge in Engineering Trace
- [x] T108 Add default pytest Gemini `google_search` quota protection (`RUN_LIVE_GROUNDING=1` opt-in) plus unit tests for `429 RESOURCE_EXHAUSTED` -> Ollama failover, clean bullet stripping, and `./data/research_cache/` cache hit; run `python -m pytest backend/tests/ -v` and `npm run build` in `frontend/`
- [x] T109 Enforce IPv4 `127.0.0.1` Ollama defaults, `"think": False` & `"keep_alive": "15m"` Ollama `/api/chat` payloads, `90.0s` (`connect=5.0`) Ollama timeouts across `failover_client.py` / specialists / orchestrator, `120.0s` A2A client timeouts, and full prefix/blank bullet stripping across `research_agent.py`, `presentation_agent.py`, and `WebIntelligenceCard.tsx`
- [x] T110 Cap Ollama CPU context/generation (`"options": {"num_ctx": 1024, "num_predict": 180, "temperature": 0.3}`), bump Ollama timeouts to `150.0s` (`180.0s` A2A hop timeout), add 60s Gemini `429 RESOURCE_EXHAUSTED` cooldown & elapsed-time exception logging in `failover_client.py`, keep `ResearchAgent` prompt concise (~120 words), eliminate alternating blank `- ` bullets cleanly, and verify with `pytest` + `npm run build`

---

## Phase 14: Single-Column Conversational HUD Redesign

**Purpose**: Redesign the React frontend (`frontend/src/`) from a 2-column split screen with persistent preset list into a ChatGPT/Gemini-style single-column centered conversational HUD on `#0B0F17`, attaching visual artifacts and traces per assistant turn (`Status -> Visual Artifact -> Prose -> Collapsible Trace`).

- [x] T111 Update `frontend/src/types/index.ts` and refactor `frontend/src/hooks/useSSEStream.ts` so each assistant `ChatMessage` owns its own `chart` (`PlotlySpec`), `minimap` (`PlotlySpec`), `trace` (`EngineeringTrace`), and `status` (`string | null`) rather than overwriting global right-panel state, ensuring an assistant placeholder turn is created when `status`, `chart`, `text`, or `trace` arrives first
- [x] T112 Update `frontend/src/components/ChartStage/PlotlyChart.tsx`, `TrackMiniMap.tsx`, and `ChartStage.tsx` for full-width responsive inline rendering (`useResizeHandler={true}`, `autosize: true`), driver/metadata badges, empty-state omission when inline, and a modal/fullscreen expand toggle for Plotly figures
- [x] T113 Refactor `frontend/src/components/EngineeringTrace/TraceDrawer.tsx` into a compact single-line collapsed bar by default displaying A2A hop count, provider (`gemini` / `ollama_fallback` / `cache`), and execution latency (`ms`), expanding on click to show full A2A breadcrumbs, `dataset_id`, SQL, telemetry/strategy params, and grounding sources
- [x] T114 Build `WelcomeHero.tsx` (centered hero + 2x2 starter prompt cards when `messages.length === 0`), compact Quick-Prompts popover in `PresetPrompts.tsx`, `TurnItem.tsx` (`max-w-5xl` per-turn vertical flow: Live Status Pill -> Visual Artifact -> Race Engineer Markdown -> Collapsible Trace Bar), and floating bottom pill `ComposerBar.tsx` (`max-w-3xl`, popover trigger, auto-growing textarea, Voice Pit-Wall Radio mic slot, Send button)
- [x] T115 Replace the 2-column split layout in `frontend/src/App.tsx` with the centered single-column conversational HUD, keeping the slim top bar (`F1 PITWALL AI`, `DUCKDB`, `FASTF1`, `+ New Session`, sign out) and smooth auto-scroll to newest turns
- [x] T116 Run `npm run build` in `frontend/` and verify zero TypeScript/Vite errors and no backend SSE contract breakage (`pytest backend/tests/ -v` if needed)

---

## Phase 15: 4-Tier Cascading LLM Failover (Gemini → Groq → OpenRouter → Local Ollama)

**Purpose**: Upgrade `backend/app/config.py` and `backend/app/llm/failover_client.py` to support a 4-tier cascading failover chain with independent 60s `429` circuit breakers, `APP_ENV` / `ENABLE_OLLAMA_FALLBACK` production gating, and honest provider badges in `WebIntelligenceCard` & `TraceDrawer`.

- [x] T117 Add `APP_ENV`, `ENABLE_OLLAMA_FALLBACK` (auto-resolved from `APP_ENV` when `None`), `GROQ_API_KEY`, `GROQ_BASE_URL`, `GROQ_MODEL`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, and `OPENROUTER_MODEL` settings to `backend/app/config.py`
- [x] T118 Upgrade `backend/app/llm/failover_client.py` (and exports in `backend/app/llm/__init__.py`) with per-provider 60s `429` cooldown circuit breakers (`"gemini"`, `"groq"`, `"openrouter"`), unified OpenAI-compatible sync & SSE streaming helpers for Groq (`timeout=30.0`, trimmed context for 8K TPM budget) and OpenRouter (`timeout=35.0`, optional `HTTP-Referer` & `X-Title: PitWall AI` headers), `APP_ENV`-gated Ollama fallback (`qwen3.5:4b`, `num_ctx: 1024`, `num_predict: 180`, `think: False`, `timeout=150.0`), and sanitized error logging across `research_agent.py` & `orchestrator.py`
- [x] T119 Update provider attribution across `backend/app/a2a/agents/presentation_agent.py`, `frontend/src/types/index.ts`, `frontend/src/components/ChartStage/WebIntelligenceCard.tsx`, and `frontend/src/components/EngineeringTrace/TraceDrawer.tsx` to display `"Google Search Grounding"` (`gemini`), `"Cached Search Grounding"` (`cache`), `"Groq Cloud Fallback — No Live Search"` (`groq_fallback`), `"OpenRouter Free Fallback — No Live Search"` (`openrouter_fallback`), and `"Local Ollama Fallback — Offline Model"` (`ollama_fallback`)
- [x] T120 Add unit tests in `backend/tests/test_llm_failover_and_research_cache.py` mocking the full cascade (Gemini `429` -> Groq `200`; Gemini `429` + Groq `429` -> OpenRouter `200`; all cloud fail in `APP_ENV=local` -> Ollama runs; all cloud fail in `APP_ENV=production` -> Ollama skipped cleanly without probing `127.0.0.1:11434`, plus streaming cascade & per-provider cooldown checks)
- [x] T121 Run `python -m pytest backend/tests/ -v` and `npm run build` in `frontend/` and mark Phase 15 complete

---

## Phase 16: $0 Cloud Deployment Hardening & Containerization

**Purpose**: Prepare PitWall AI for scalable $0 cloud deployment (Vercel/Cloudflare Pages frontend + Hugging Face Spaces Docker / Cloud Run FastAPI backend with embedded read-only DuckDB).

- [x] T122 Add `CORS_ORIGINS` (comma-separated string parsed cleanly), `CACHE_DIR` (`./data` local / `/tmp/pitwall_cache` production), `REDIS_URL`, and `RATE_LIMIT_PER_MIN` (`15`) to `backend/app/config.py`, update `CORSMiddleware` + `GET /health` in `backend/app/main.py`, and ensure SSE anti-buffering headers (`Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`) on `POST /api/chat/stream`
- [x] T123 Add 30-min TTL + 200-item max cap eviction to `ArtifactStore` (`backend/app/a2a/artifact_store.py`), add read-through/write-through `QueryResponseCache` (`backend/app/cache/query_cache.py`, optional `REDIS_URL` or 128-item TTL LRU) integrated into `orchestrator.py`, guard FastF1 `session.load()` with `asyncio.Semaphore(2)` & `{CACHE_DIR}/fastf1` fallback (`backend/app/data/fastf1_cache.py`), read seeded `./data/research_cache/` while writing runtime research cache to `{CACHE_DIR}/research_cache` (`research_agent.py`), and add per-IP sliding-window rate limiting (`RATE_LIMIT_PER_MIN`) on `POST /api/chat/stream` returning HTTP 429
- [x] T124 Update `frontend/src/services/api.ts` (and `useAuth.ts` / `useSSEStream.ts`) to resolve `API_BASE` dynamically from `import.meta.env.VITE_API_URL || "http://localhost:8000"`, and create `frontend/.env.example` + `frontend/vercel.json`
- [x] T125 Add `redis>=5.0.0` to `backend/requirements.txt` and create root `Dockerfile` (Python 3.11+ slim, `uid=1000`, `APP_ENV=production`, `CACHE_DIR=/tmp/pitwall_cache`, uvicorn `${PORT:-7860}`) and `.dockerignore`
- [x] T126 Create `backend/tests/test_deployment_hardening.py` testing `ArtifactStore` TTL/max-cap eviction, per-IP HTTP 429 rate limiting, Query Response Cache 0-LLM repeat hits, `X-Accel-Buffering: no` SSE header, and `APP_ENV=production` Ollama disablement
- [x] T127 Run `python -m pytest backend/tests/ -v` and `npm run build` in `frontend/` and mark Phase 16 complete

---

## Dependencies & Execution Order

### Phase Dependencies

```mermaid
flowchart TD
    P1["Phase 1: Setup"] --> P2["Phase 2: Foundational"]
    P2 --> P3["Phase 3: US1 - Historical Q&A (P1) [MVP]"]
    P2 --> P4["Phase 4: US2 - Corner Telemetry (P1)"]
    P2 --> P5["Phase 5: US3 - Full-Lap Telemetry (P2)"]
    P2 --> P6["Phase 6: US4 - Tyre Stint Degradation (P2)"]
    P2 --> P7["Phase 7: US5 - Race Position Evolution (P2)"]
    P2 --> P8["Phase 8: US6 - Ad-Hoc Sandbox (P3)"]
    P2 --> P9["Phase 9: US7 - Live Streaming & 2018 Guard (P3)"]
    P2 --> P10["Phase 10: US8 - Winner Prediction (P3)"]
    P3 --> P11["Phase 11: Polish & E2E Validation"]
    P4 --> P11
    P5 --> P11
    P6 --> P11
    P7 --> P11
    P8 --> P11
    P9 --> P11
    P10 --> P11
```

### User Story Dependencies

- **US1 (Historical Q&A - P1)**: Depends only on Phase 2 (DuckDB, auth, basic chat UI). Independent of all telemetry stories.
- **US2 (Corner Telemetry - P1)**: Depends on Phase 2 (FastF1 cache, entity resolver, Plotly stage). Can run in parallel with US1.
- **US3 (Full-Lap Telemetry - P2)**: Reuses telemetry loading from US2 (T030) and Plotly stage.
- **US4 (Tyre Degradation - P2)**: Reuses FastF1 session data and DuckDB stint definitions. Independent of corner slicing.
- **US5 (Position Evolution - P2)**: Reuses DuckDB `lap_times` and team colors from Phase 2. Independent of telemetry.
- **US6 (Ad-Hoc Sandbox - P3)**: Reuses DuckDB connection and Plotly theme. Independent of specific chart builders.
- **US7 (Live Streaming - P3)**: Hooks into SSE streaming pipeline established in Phase 2.
- **US8 (Prediction - P3)**: Reuses historical results querying from US1.

---

## Parallel Execution Opportunities

### Phase 1 & 2 Parallel Tracks
- `backend/requirements.txt` (T001) in parallel with `frontend/package.json` (T002)
- `duckdb_manager.py` (T006) in parallel with `fastf1_cache.py` (T009) and `entity_resolver.py` (T010)
- `auth/dependencies.py` (T012) in parallel with `chat/session.py` (T013) and `charts/plotly_theme.py` (T015)

### User Story 1 Parallel Track
- Tests (T017, T018, T019) written first
- Backend tools (T020, T021) in parallel with Frontend components (T024, T025)

### User Story 2 Parallel Track
- Entity resolver tests (T028) and corner slicing tests (T029) written first
- Telemetry loader (T030) and team color resolver (T031) in parallel with mini-map (T038) and metadata bar (T037)

---

## Implementation Strategy

### MVP First (Phases 1, 2, and 3)
1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1: Historical F1 Q&A).
3. **Validate MVP**: Run `pytest backend/tests/test_duckdb_ingestion.py` and test query "Who won the 2023 Bahrain Grand Prix?". At this point, the platform is already a viable, useful F1 analytics engine.

### Incremental Delivery
1. Add User Story 2 (Corner Telemetry) → Unlock signature race-engineer differentiator.
2. Add User Stories 3, 4, 5 (Full-Lap, Tyres, Position) → Complete full race weekend analysis suite.
3. Add User Stories 6, 7, 8 (Ad-hoc, Streaming, Predictions) → Complete advanced analytical suite.
4. Run Phase 11 (Polish & Playwright E2E) → Production ready.
