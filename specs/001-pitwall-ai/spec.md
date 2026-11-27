# Feature Specification: PitWall AI — F1 Race Engineer

**Feature Branch**: `001-pitwall-ai`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Build PitWall AI, an AI Race Engineer web app that answers natural-language Formula 1 questions from 1950 to 2024+ with interactive visualizations."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Historical F1 Question Answering (Priority: P1)

A user opens PitWall AI, types a natural-language question about Formula 1 history (e.g., "How many wins did Ayrton Senna have in 1991?" or "Which constructor has the most championships?"), and receives an accurate answer accompanied by an interactive chart or table and the exact SQL query that produced the data.

**Why this priority**: This is the broadest-reach capability. It covers 75 years of F1 data (1950–2024+), serves the widest range of questions, and validates the core zero-hallucination pipeline end-to-end: natural language → SQL generation → query execution → result visualization.

**Independent Test**: Can be fully tested by submitting historical questions and verifying answers against official FIA/F1 records. Delivers immediate standalone value.

**Acceptance Scenarios**:

1. **Given** the user types "Who won the 2023 Bahrain Grand Prix?", **When** the system processes the question, **Then** it returns "Max Verstappen" with a results table showing the top-10 classification, an interactive chart of the finishing order, and a collapsible Engineering Trace panel displaying the exact DuckDB SQL query executed.
2. **Given** the user asks "Show me Lewis Hamilton's podium finishes per season", **When** the system processes the query, **Then** it returns an interactive bar chart with one bar per season, correct podium counts matching official records, and the SQL query visible in the Engineering Trace.
3. **Given** the user asks a question about a driver or race that does not exist in the database, **When** the system cannot find matching data, **Then** it returns a clear "No data found" message rather than fabricating a response.

---

### User Story 2 - Corner-by-Corner Telemetry Comparison (Priority: P1)

A user asks to compare two drivers through a specific corner (by turn number or famous nickname like "Eau Rouge," "Copse," or "130R") for a given session. PitWall AI loads the telemetry, slices the entry-apex-exit zone (±200m around the corner), and renders a synchronized multi-panel interactive chart showing Speed, Speed Delta, Throttle, Brake, and Gear traces, plus a zoomed GPS track mini-map colored by which driver is faster. The system defaults to Qualifying fastest laps when the user does not specify a session.

**Why this priority**: This is the signature differentiating feature — no existing public tool offers corner-level comparison with an AI race-engineer explanation. It exercises the full telemetry pipeline and the most complex visualization.

**Independent Test**: Can be tested by requesting a known corner comparison (e.g., "Compare Verstappen and Leclerc through Copse at the 2023 British GP Qualifying") and verifying computed metrics (braking point delta, apex min speed, lowest gear, full-throttle pickup point, corner time delta) against manually computed values from the same FastF1 data.

**Acceptance Scenarios**:

1. **Given** the user asks "Compare Verstappen and Leclerc through Eau Rouge at the 2023 Belgian GP", **When** the session is not specified, **Then** the system defaults to Qualifying fastest laps, loads FastF1 telemetry, renders the multi-panel chart (Speed, Delta, Throttle, Brake, Gear), displays the GPS mini-map colored by faster driver, computes the five corner metrics, and provides race-engineer commentary grounded in the computed numbers.
2. **Given** the user specifies a turn number instead of a name (e.g., "Turn 7 at Monza"), **When** the system processes the request, **Then** it correctly maps the turn number to the corner coordinates and produces the same comparison output.
3. **Given** telemetry data is not available for the requested session (e.g., a pre-2018 race), **When** the system detects this, **Then** it explains the 2018 boundary for car telemetry data clearly and suggests alternative historical analyses that are available.

---

### User Story 3 - Full-Lap Telemetry Overlay (Priority: P2)

A user asks to overlay two drivers' full-lap telemetry for a given session. PitWall AI renders an interactive speed trace, throttle/brake map, and gear usage chart across the entire lap with driver traces colored by official F1 team colors.

**Why this priority**: Full-lap overlays are a natural complement to corner comparisons and serve users who want the big picture before drilling into specific corners. Reuses the same telemetry loading infrastructure.

**Independent Test**: Can be tested by requesting a full-lap overlay for two drivers in a known session and comparing the rendered speed trace against the raw FastF1 channel data.

**Acceptance Scenarios**:

1. **Given** the user asks "Overlay Verstappen vs Hamilton full lap at 2023 Abu Dhabi Qualifying", **When** the system loads both drivers' fastest qualifying laps, **Then** it renders a synchronized speed trace with correct official team colors, displays lap time and delta, and shows session metadata (GP, year, session type, lap number, compound).
2. **Given** one driver did not set a valid lap in the session, **When** the system detects missing data, **Then** it informs the user which driver's data is unavailable and offers alternative sessions.

---

### User Story 4 - Tyre Stint Degradation Analysis (Priority: P2)

A user asks about tyre degradation for a driver during a race. PitWall AI filters out pit-in/pit-out laps and Safety Car laps, then charts lap time progression per stint, colored by compound, with a degradation trend line.

**Why this priority**: Tyre strategy is central to F1 race engineering. This feature builds on the race data pipeline and adds stint-level analysis that is directly actionable for understanding race strategy.

**Independent Test**: Can be tested by loading a known race, verifying that pit laps and Safety Car laps are excluded from the degradation chart, and checking lap times against official timing data.

**Acceptance Scenarios**:

1. **Given** the user asks "Show me Verstappen's tyre degradation at the 2023 Spanish GP", **When** the system processes the request, **Then** it displays a chart of lap times per stint, colored by tyre compound, with pit and Safety Car laps excluded, a degradation trend line per stint, and session metadata.
2. **Given** a race had a red flag, **When** the system processes the data, **Then** it correctly handles the interrupted session and indicates the red-flag period in the visualization.

---

### User Story 5 - Race Position Evolution (Priority: P2)

A user asks to see how race positions changed throughout a Grand Prix. PitWall AI renders a "spaghetti plot" showing each driver's position on each lap, colored by team colors, with key events (pit stops, retirements, Safety Cars) annotated.

**Why this priority**: Position charts are the most common race-analysis visualization in F1 broadcasting and fan communities. They tie together pit strategy and on-track action.

**Independent Test**: Can be tested by rendering a position chart for a known race and verifying final positions against official classification.

**Acceptance Scenarios**:

1. **Given** the user asks "Show me the race position chart for the 2023 Brazilian GP", **When** the system renders the chart, **Then** each driver's trace uses the correct team color, final positions match the official classification, and pit-stop laps are marked.
2. **Given** the user clicks on a driver's trace, **When** they interact with the chart, **Then** the driver's line is highlighted and a tooltip shows lap-by-lap details.

---

### User Story 6 - Ad-Hoc Cross-Metric Analysis (Priority: P3)

A user asks a custom question that does not map to any preset chart type (e.g., "Plot average pit stop duration per team across the last 5 seasons" or "What is the correlation between qualifying position and race finish at Monaco?"). PitWall AI determines the appropriate analysis, executes safe deterministic computations, and returns an interactive chart with the computation trace.

**Why this priority**: Covers the long tail of user questions that cannot be anticipated. Requires the most flexible analysis pipeline but builds on the same SQL and Python execution infrastructure.

**Independent Test**: Can be tested by submitting diverse custom queries and verifying that every returned chart has a valid computation trace and accurate numbers.

**Acceptance Scenarios**:

1. **Given** the user asks "What is the average pit stop duration per team in 2023?", **When** the system processes the request, **Then** it generates the appropriate SQL query, executes it, and renders a bar chart with team-colored bars showing average pit stop durations, with the SQL query visible in the Engineering Trace.
2. **Given** the user asks a question that requires combining historical and telemetry data, **When** the system detects the cross-domain query, **Then** it clearly labels which data comes from the historical SQL domain and which from the telemetry domain.

---

### User Story 7 - Live Progress Streaming & 2018 Boundary Explanation (Priority: P3)

While any analysis is loading, the user sees a step-by-step streaming progress feed showing what PitWall AI is doing (e.g., "Loading FastF1 session data…", "Executing SQL query…", "Computing braking deltas…"). When a user asks for car telemetry from before 2018, the system gracefully explains the data boundary.

**Why this priority**: Telemetry loading can take several seconds. Streaming progress prevents user frustration and builds trust in the computation pipeline. The 2018 boundary explanation prevents confusion.

**Independent Test**: Can be tested by timing a telemetry-heavy request and confirming that progress messages appear before the final result, and by asking for pre-2018 telemetry to verify the boundary explanation.

**Acceptance Scenarios**:

1. **Given** the user submits a telemetry comparison request, **When** the data is loading, **Then** the UI streams status messages (e.g., "Loading 2023 Belgian GP Qualifying session…", "Extracting VER fastest lap…", "Slicing Eau Rouge corridor…") in real time before the final chart appears.
2. **Given** the user asks "Show me Schumacher's telemetry at the 2004 Italian GP", **When** the system detects this is before 2018, **Then** it displays a clear explanation: "Car telemetry data is available from the 2018 season onwards. For 2004 and earlier seasons, I can provide historical race results, lap times, and championship standings."

---

### User Story 8 - Winner Prediction (Priority: P3)

A user asks "Who will win at Monza this year?" or "Who's the championship favorite?" PitWall AI analyzes recent form data for teams and drivers — recent race results, qualifying performance, circuit-specific history — and presents a prediction with confidence factors, all grounded in computed statistics, not LLM opinion.

**Why this priority**: Prediction adds a forward-looking engagement dimension. However, it must be built on the verified historical analytics pipeline and clearly communicated as a data-driven projection, not a guarantee.

**Independent Test**: Can be tested by verifying that every statistic cited in the prediction output traces back to a SQL query or computed metric, and that the confidence factors are based on explicit criteria.

**Acceptance Scenarios**:

1. **Given** the user asks "Who will win the next race at Silverstone?", **When** the system processes the request, **Then** it displays a ranked prediction with percentage-based confidence scores, backed by explicit factors (recent form, circuit history, qualifying pace), each with a traceable SQL query or computation in the Engineering Trace.
2. **Given** insufficient recent data exists for a meaningful prediction, **When** the system detects this, **Then** it states that the prediction confidence is low and explains what data is missing.

---

### Edge Cases

- What happens when a user asks for telemetry from a sprint session that only had a sprint qualifying format (post-2023 format changes)?
- How does the system handle a wet-weather qualifying session where some drivers did not set a representative lap?
- What happens when two team colors are nearly identical on the dark HUD background (e.g., AlphaTauri blue vs Williams blue)?
- How does the system respond when a user asks about a future season for which no data exists yet?
- What happens when FastF1 session data is temporarily unavailable or corrupted? The system serves from local cache if available (indicating staleness), retries 1–2 times on transient errors, and fails with a clear error only if no cache exists.
- How does the system handle corner nicknames that apply to different corners at different circuits (e.g., if a nickname is ambiguous)?
- What happens when a race was red-flagged and restarted, producing two sets of stint data?
- How does the system handle historical races with incomplete or missing timing data (pre-1980s)?

## Clarifications

### Session 2026-11-22

- Q: Does PitWall AI require user authentication to access, or is it open public? → A: Authenticated — users must sign in (email, OAuth, or similar) to access the app.
- Q: Is PitWall AI single-shot Q&A or multi-turn conversation with memory? → A: Multi-turn within a session (rolling summary + last 4–6 turns verbatim), stateless across sessions.
- Q: What safety boundary constrains ad-hoc Python execution for custom analysis? → A: LLM-generated Python runs in a restricted sandbox with no filesystem access, no network access, and a strict execution timeout.
- Q: When FastF1 is unavailable at runtime, what is the fallback behavior? → A: Cache-first fallback — serve from local cache if available (indicating data freshness to the user), plus 1–2 retries on transient timeouts before failing with an error if no cache exists.
- Q: What is the target number of concurrent authenticated users for initial release? → A: 5–10 concurrent users.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept natural-language questions about Formula 1 and determine whether the question requires historical SQL data, car telemetry data, or both.
- **FR-002**: System MUST generate and execute deterministic DuckDB SQL queries for all historical data questions (1950–2024+). No number may be produced from LLM memory.
- **FR-003**: System MUST load and process car telemetry via FastF1 for all telemetry-based analyses (2018+ seasons only). When FastF1 is unavailable, the system MUST first attempt to serve from local cache (indicating data freshness to the user). If no cache exists, the system MUST retry 1–2 times on transient timeouts before returning an explicit error message.
- **FR-004**: System MUST render corner-by-corner telemetry comparisons showing synchronized Speed, Speed Delta, Throttle, Brake, and Gear panels for a user-specified corner (by turn number or famous nickname), sliced across an entry-apex-exit window of approximately ±200 meters around the corner reference point.
- **FR-005**: System MUST compute five corner metrics for every corner comparison: braking point delta, apex minimum speed, lowest gear, full-throttle pickup point, and corner time delta.
- **FR-006**: System MUST render a zoomed GPS track mini-map for corner comparisons, colored by which driver is faster through each segment.
- **FR-007**: System MUST default to Qualifying fastest laps when the user does not specify a session type for telemetry comparisons.
- **FR-008**: System MUST render full-lap telemetry overlays comparing two drivers across an entire lap.
- **FR-009**: System MUST chart tyre stint degradation, filtering out pit-in/pit-out laps and Safety Car laps, with traces colored by compound type.
- **FR-010**: System MUST render race position evolution charts showing each driver's position per lap, colored by official team colors, with pit-stop and Safety Car annotations.
- **FR-011**: System MUST handle ad-hoc cross-metric questions by generating safe deterministic Python or SQL computations and returning interactive charts. All LLM-generated Python code MUST execute inside a restricted sandbox with no filesystem access, no network access, and a strict execution timeout. If execution exceeds the timeout or attempts a forbidden operation, the system MUST return an error rather than a partial or unsafe result.
- **FR-012**: System MUST stream step-by-step progress messages to the UI while loading data and performing computations.
- **FR-013**: System MUST gracefully explain the 2018 telemetry boundary when a user requests car telemetry from an earlier season, and suggest available historical alternatives.
- **FR-014**: System MUST display a collapsible Engineering Trace panel alongside every result, showing the exact SQL query or telemetry parameters used.
- **FR-015**: System MUST use official F1 team colors (sourced from a canonical registry, not hardcoded) for all driver and team visual encodings, correct for the depicted season.
- **FR-016**: System MUST display session and lap metadata (Grand Prix name, year, session type, lap number, driver code, compound, weather conditions) on every data visualization.
- **FR-017**: System MUST render all telemetry visualizations on a dark HUD background (#0B0F17) with WCAG AA compliant text contrast.
- **FR-018**: System MUST provide winner and championship predictions grounded in computed statistics (recent form, circuit history, qualifying pace) with explicit confidence factors and traceable computation sources.
- **FR-019**: System MUST provide race-engineer style natural-language commentary on telemetry comparisons, grounded exclusively in the computed metrics.
- **FR-020**: System MUST correctly identify corners by famous nickname (e.g., Copse, Eau Rouge, Maggotts-Becketts, 130R, Parabolica) and map them to the correct track distance (meters) and turn number.
- **FR-021**: All interactive charts MUST support hover tooltips, zoom, and pan interactions.
- **FR-022**: System MUST require user authentication (sign-in) before granting access to any feature. Unauthenticated users MUST be redirected to a login screen.
- **FR-023**: System MUST support multi-turn conversation within a session, allowing follow-up questions that reference previous context (e.g., "Now show his teammate's lap"). Context MUST be maintained via a rolling summary plus the last 4–6 turns verbatim.
- **FR-024**: System MUST be stateless across sessions — no conversation history persists after a session ends. Each new session starts with a clean context.
- **FR-025 (Single-Row KPI Card, Table Fallback & Clean Text Contract)**: System MUST NEVER emit or mount an empty Plotly `data: []` canvas and MUST NEVER leak internal specialist summaries (`"Retrieved X rows across columns..."`, `"Dataset stored under dataset_id=..."`) into Plotly `layout.title` or user-facing chat `text` (`dataset_id` belongs strictly in the `trace` event). When `historical_sql` returns `row_count == 1`, `PresentationAgent` MUST return `{ viz_type: "kpi_card", title: "<clean human title>", kpi_card: { subtitle: "<race/year>", metrics: [{ label, value }] } }` and `ChartStage` MUST render a dark `#0B0F17` HUD Result KPI Card. When `historical_sql` returns `row_count >= 2` without a suitable numeric y-axis bar chart, `PresentationAgent` and `ChartStage` MUST render a dark `#0B0F17` HUD Data Table (`viz_type: "data_table"`).
- **FR-026 (SSE `viz_type` Top-Level Preservation & Faster-Driver Attribution)**: Every SSE `chart` event MUST preserve top-level `viz_type` (`"corner_telemetry"`, `"full_lap"`, `"tyre_stints"`, `"historical_sql"`, `"kpi_card"`, `"data_table"`, `"web_intelligence_card"`) alongside `figure`, `kpi_card`, `data_table`, or `web_intelligence_card`, so `ChartStage` switches cleanly on `viz_type`. `TelemetryAgent.compare_full_lap` MUST explicitly emit `driver_1_lap_time`, `driver_2_lap_time`, and `faster_driver` fields in its summary/metrics payload so `PitWallEngineer` cannot invert who set the faster lap.
- **FR-027 (Historical SQL & Narration Latency Optimization)**: Keeping the existing configured `GEMINI_MODEL` in `.env` intact, `HistoricalSQLAgent` SQL generation and `PitWallEngineer` narration MUST configure minimal thinking (`thinking_budget=0` on Gemini 2.5 Flash models or lowest supported `thinking_level` for the configured model, guarded cleanly for unsupported models) to keep simple historical lookups in the ~1–2s range.
- **FR-028 (Unified Gemini → Local Ollama Runtime Failover)**: Backend MUST provide a shared LLM helper (`backend/app/llm/`) used by `PitWallEngineer`, `HistoricalSQLAgent`, and `ResearchAgent` keeping Gemini configuration purely env-driven (`GEMINI_API_KEY` / `GOOGLE_API_KEY`, `GEMINI_MODEL`, and optional `GOOGLE_GENAI_USE_VERTEXAI` / `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION`). On ANY runtime Gemini failure (`429` / `RESOURCE_EXHAUSTED`, `503`, timeouts, missing key), the helper MUST automatically fail over to local Ollama over IPv4 (`OLLAMA_BASE_URL`, default `http://127.0.0.1:11434/api/chat`; `OLLAMA_API_BASE`, default `http://127.0.0.1:11434`; `OLLAMA_MODEL`, default `qwen3.5:4b`, sending `"think": false`, `"keep_alive": "15m"`, `"options": {"num_ctx": 1024, "num_predict": 180, "temperature": 0.3}`, `150.0s` read / `5.0s` connect timeout, and `180.0s` A2A hop timeout). On `429 RESOURCE_EXHAUSTED`, the helper MUST enter a 60-second Gemini cooldown skipping redundant Gemini calls in that window. All Gemini/Ollama exceptions MUST be logged server-side with elapsed time and exception class via `logger.warning`, NEVER leaking raw exception dicts or tracebacks into UI summaries, bullets, or chat text, and MUST record `"provider": "gemini" | "ollama_fallback" | "cache"` in SSE `trace` events.
- **FR-029 (`ResearchAgent` Disk Cache & Local Fallback Contract)**: `ResearchAgent` MUST execute in strict priority order: (1) `./data/research_cache/` disk cache returning `grounded=True` responses with `0` API calls (`provider="cache"`); (2) Gemini + `google_search` grounding storing successful grounded responses in `./data/research_cache/` (`provider="gemini"`); (3) local Ollama fallback generating concise F1 summary & non-empty bullet takeaways (`grounded=False`, `provider="ollama_fallback"`, `sources=[]`); (4) clean user-safe fallback notice only if Ollama is also unreachable. Empty/whitespace bullets MUST be stripped. `WebIntelligenceCard` MUST show `"Google Search Grounding"` ONLY when `grounded === true` and `"Local Ollama Fallback (Offline Model)"` when `grounded === false`.
- **FR-030 (Pytest API Quota Protection)**: Automated tests in `backend/tests/` MUST mock live Gemini `google_search` calls by default unless `RUN_LIVE_GROUNDING=1` is set, while verifying `429 RESOURCE_EXHAUSTED` automatic failover to Ollama and zero-API-call disk cache hits on repeated queries.
- **FR-031 (Single-Column Conversational HUD & Per-Turn Inline Feed)**: The React HUD (`frontend/src/`) MUST present a centered single-column ChatGPT/Gemini-style conversational layout on `#0B0F17` (replacing the 2-column split screen and persistent 11-button sidebar):
  1. Slim top HUD header bar displaying `F1 PITWALL AI`, `DUCKDB` / `FASTF1` status pills, user identity/logout, and a `+ New Session` button resetting the conversation thread cleanly.
  2. Empty-state Welcome View (`messages.length === 0`) displaying a centered PitWall AI hero header and a 2x2 grid of 4 concise starter prompt cards (Corner Telemetry, Full-Lap Overlay, Tyre Stints, Historical/Research) that disappears once the first message is sent.
  3. Per-turn inline conversation feed (`max-w-5xl` centered) where every assistant message owns its own `chart` / `vizPayload` (`figure`, `kpi_card`, `data_table`, `web_intelligence_card`), optional `minimap`, and `trace` payload, rendered vertically in strict order: (a) live status pill while streaming (auto-hides on content), (b) full-width visual artifact on top (responsive Plotly chart with `useResizeHandler={true}`, driver/metadata badges, and modal/fullscreen expand toggle, or dark HUD `KpiCard` / `DataTableCard` / `WebIntelligenceCard`), (c) Race Engineer markdown prose below, and (d) compact single-line collapsible Engineering Trace bar (A2A hops, provider badge `gemini` / `ollama_fallback` / `cache`, execution latency) expanding into the full `TraceDrawer`.
  4. Centered floating dark pill composer pinned to the bottom (`max-w-3xl`) featuring a compact Quick-Prompts popover button (lightning-bolt trigger opening categorized demo presets on demand), auto-growing textarea, reserved Pit-Wall Voice Radio mic slot, and Send button, with smooth auto-scroll to newest turns while keeping prior charts/cards scrollable in history.

### Key Entities

- **Driver**: A Formula 1 driver identified by code, full name, nationality, and career span. Associated with one or more Constructors per season.
- **Constructor**: A Formula 1 team identified by name, nationality, and active seasons. Associated with one or two Drivers per season and a team color palette per season.
- **Race / Grand Prix**: A race event identified by name, circuit, season year, round number, and date. Contains Results, Lap Times, Pit Stops, and optionally Telemetry Sessions.
- **Session**: A specific track session (FP1, FP2, FP3, Qualifying, Sprint, Race) within a Grand Prix weekend. For 2018+ sessions, may contain car Telemetry data.
- **Telemetry Lap**: A single timed lap within a Session, containing channel data (Speed, Throttle, Brake, Gear, RPM, DRS, X/Y/Z position) at sub-second intervals.
- **Corner / Turn**: A defined section of a Circuit identified by turn number and optionally a famous nickname. Used as the reference point for entry-apex-exit slicing.
- **Stint**: A contiguous run of laps on the same tyre compound within a Race, bounded by pit stops or session start/end.
- **User Account**: An authenticated identity with a unique identifier, used to gate access to PitWall AI. Associated with a login method (email/password, OAuth, or similar).
- **Conversation Session**: A single continuous interaction session between a user and PitWall AI. Contains a rolling summary of earlier turns plus the last 4–6 turns verbatim for context resolution. Not persisted after the session ends.
- **Prediction**: A data-driven projection of race or championship outcomes, containing ranked candidates, confidence scores, and the statistical factors that produced them.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive accurate answers to historical F1 questions within 5 seconds for SQL-based queries. Accuracy is verified against official FIA records with 100% correctness for factual lookups.
- **SC-002**: Corner-by-corner telemetry comparisons load and render within 15 seconds, including data retrieval, computation, and chart rendering.
- **SC-003**: Every user-facing number in every response traces back to a verifiable SQL query or deterministic computation — zero numbers produced from LLM memory (zero-hallucination guarantee).
- **SC-004**: 100% of telemetry visualizations render on the dark HUD background with correct team colors and WCAG AA text contrast.
- **SC-005**: The Engineering Trace panel is present and populated for 100% of data-bearing responses.
- **SC-006**: The system correctly explains the 2018 telemetry boundary 100% of the time when users request pre-2018 car telemetry, offering relevant historical alternatives.
- **SC-007**: Users can ask any historical F1 question spanning 1950–2024+ and receive a chart, table, or combined visualization — covering drivers, constructors, circuits, seasons, pit stops, and championship standings.
- **SC-008**: Automated pytest suites covering all features pass against real race data with no synthetic mocks for user-facing computations.
- **SC-009**: Winner predictions include explicit confidence factors and every cited statistic is traceable to a computed source.
- **SC-010**: Users experience streaming progress feedback for any operation that takes longer than 2 seconds.

## Assumptions

- Users have a modern web browser with support for interactive charting (canvas/SVG rendering).
- The FastF1 library provides reliable access to telemetry data for 2018+ seasons; the system depends on FastF1's data availability and caching infrastructure.
- Historical race data (1950–2024+) is pre-loaded into a DuckDB database sourced from Ergast or equivalent official F1 data repositories.
- Corner nickname-to-coordinate mappings are maintained as a curated reference dataset within the application.
- The application requires authentication; all users must sign in before accessing any feature.
- The application targets 5–10 concurrent authenticated users for the initial release; high-concurrency scaling is out of scope for the initial version.
- Mobile-responsive design is a secondary concern; the primary interface targets desktop/laptop screens where telemetry charts are readable.
- The system does not provide real-time live timing during active race sessions; it analyzes completed sessions only.
- Winner predictions are explicitly framed as data-driven projections, not guarantees, and are based on historical and recent performance data only.
