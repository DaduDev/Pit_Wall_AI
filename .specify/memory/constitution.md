<!--
╔══════════════════════════════════════════════════════════════╗
║                   SYNC IMPACT REPORT                        ║
╠══════════════════════════════════════════════════════════════╣
║ Version Change : (none) → 1.0.0 (initial ratification)     ║
║                                                             ║
║ Modified Principles: N/A (first version)                    ║
║                                                             ║
║ Added Sections:                                             ║
║   - Core Principles (7 principles)                          ║
║     I.   Zero-Hallucination Math                            ║
║     II.  Data Domain Separation                             ║
║     III. Telemetry HUD Visual Standards                     ║
║     IV.  Provenance Transparency                            ║
║     V.   Automated Verification                             ║
║     VI.  Official F1 Team Colors                            ║
║     VII. Session & Lap Metadata Fidelity                    ║
║   - Data Architecture Constraints                           ║
║   - Quality & Testing Standards                             ║
║   - Governance                                              ║
║                                                             ║
║ Removed Sections : N/A (first version)                      ║
║ Deferred TODOs   : None                                     ║
╚══════════════════════════════════════════════════════════════╝
-->

# PitWall AI Constitution

## Core Principles

### I. Zero-Hallucination Math (NON-NEGOTIABLE)

The LLM MUST NEVER calculate statistics, averages, braking points, lap deltas,
or any numerical result from memory, training data, or parametric inference.

- Every number displayed to the user MUST originate from one of exactly two
  computation paths:
  1. **DuckDB SQL** — deterministic queries against structured race data.
  2. **Python / NumPy** — deterministic telemetry calculations executed at
     runtime against loaded car telemetry arrays.
- If a computation path cannot be executed (missing data, query failure), the
  system MUST surface an explicit error rather than fabricate or approximate a
  value.
- The LLM's role is to *author* SQL and Python code, *interpret* returned
  results in natural language, and *never* substitute its own arithmetic.
- Any code path that produces a user-facing number MUST be traceable to a
  SQL query string or a Python/NumPy function invocation with deterministic
  inputs.

**Rationale**: Formula 1 strategy decisions depend on sub-tenth-of-a-second
precision. A hallucinated delta or braking point can mislead analysis and
erode trust in the entire platform.

### II. Data Domain Separation

A strict boundary MUST be maintained between the two canonical data domains:

| Domain | Source | Coverage | Storage |
|---|---|---|---|
| Historical Race Data | Ergast / official F1 results | 1950 – 2024+ | DuckDB |
| Car Telemetry | FastF1 API | 2018+ | In-memory / parquet cache |

- Queries and computations MUST NOT conflate data from different domains in a
  single result without explicitly labeling which domain each datum originates
  from.
- Historical queries against seasons before 2018 MUST NOT reference telemetry
  columns; telemetry queries MUST NOT reference historical-only tables as if
  they contain channel data.
- When a user request spans both domains (e.g., "Compare Senna's 1991 wins
  with Verstappen's 2023 telemetry"), the response MUST clearly demarcate
  which portion is historical SQL and which is FastF1 telemetry.

**Rationale**: Mixing heterogeneous data sources without explicit provenance
creates invisible accuracy failures and misleading cross-era comparisons.

### III. Telemetry HUD Visual Standards

All telemetry visualizations MUST render on a dark HUD background using the
canonical base color `#0B0F17`.

- Chart backgrounds, panel backgrounds, and dashboard canvases MUST use
  `#0B0F17` or a shade within ±5 lightness units in OKLCH space.
- Foreground text MUST maintain a minimum WCAG AA contrast ratio (4.5:1)
  against the HUD background.
- Grid lines, axis labels, and secondary chrome MUST use muted variants that
  do not compete with data traces.
- No telemetry chart or dashboard panel MAY use a white or light background.

**Rationale**: A consistent dark cockpit aesthetic reinforces the
professional motorsport-engineering identity, reduces eye strain during
long analysis sessions, and maximizes contrast for thin telemetry traces.

### IV. Provenance Transparency

Every feature that surfaces data to the user MUST display its provenance
chain in the UI.

- For SQL-sourced data: the exact DuckDB SQL query string (or a
  user-expandable summary) MUST be accessible from the result panel.
- For telemetry-sourced data: the FastF1 session key, lap number, driver
  code, and channel list MUST be shown alongside the visualization.
- The UI MUST expose a "Show Source" affordance (expandable section, tooltip,
  or dedicated panel) so users can inspect how any displayed number was
  derived.
- Raw computation traces (SQL, Python snippets) MUST be preserved in the
  response payload even if collapsed by default.

**Rationale**: Trust in a data platform requires that every claim be
independently auditable by the user down to the query or function call that
produced it.

### V. Automated Verification

Every user-facing feature MUST be backed by an automated pytest suite that
validates correctness against real race data.

- Tests MUST use known-good historical results (e.g., official race
  classifications, published lap times) as ground-truth fixtures.
- Telemetry feature tests MUST load real FastF1 session data (cached or
  fixture-serialized) and assert against deterministic expected outputs.
- No feature is considered complete until its pytest suite passes in CI.
- Test coverage MUST include edge cases: wet-weather sessions, red-flagged
  races, sprint weekends, and seasons with regulation changes.

**Rationale**: The zero-hallucination guarantee is only as strong as the
automated verification that enforces it on every code change.

### VI. Official F1 Team Colors

All driver and team visual encodings (chart traces, legends, badges, icons)
MUST use the officially published F1 team colors for the relevant season.

- Color assignments MUST be sourced from the FastF1 team color palette or an
  equivalent canonical registry, never from LLM memory or hard-coded
  approximations.
- When rendering multi-team comparisons, each team's primary color MUST be
  visually distinguishable on the `#0B0F17` HUD background; if two team
  colors are too similar, the secondary/accent color MUST be used for one.
- Historical visualizations MUST use the team colors correct for the depicted
  season, not the current season's palette.

**Rationale**: Incorrect team colors break visual identification and
undermine the professional quality expected of a motorsport engineering tool.

### VII. Session & Lap Metadata Fidelity

Every data display MUST include the exact session and lap metadata from which
the data was derived.

- Required metadata fields: Grand Prix name, season year, session type
  (FP1/FP2/FP3/Qualifying/Sprint/Race), and lap number(s) or lap range.
- For telemetry displays: driver code, compound type, and weather conditions
  at the time of the lap MUST be shown when available from FastF1.
- Metadata MUST be sourced from the data payload, never inferred or
  paraphrased by the LLM.

**Rationale**: Ambiguous or absent metadata makes it impossible for users to
contextualize or reproduce an analysis, violating the provenance guarantee.

## Data Architecture Constraints

- **DuckDB as single SQL engine**: All structured historical queries MUST
  execute against DuckDB. No other SQL engine (SQLite, PostgreSQL, etc.) is
  permitted for race data queries unless explicitly scoped as an integration
  adapter.
- **FastF1 as single telemetry source**: All car telemetry (speed, throttle,
  brake, gear, RPM, DRS, position channels) MUST be sourced from the FastF1
  library. No manual CSV imports or screen-scraped telemetry is permitted.
- **No LLM-side caching of numeric results**: The LLM MUST NOT store
  previously computed results in conversation context and reuse them in later
  turns without re-executing the query or computation. Each turn's numbers
  MUST come from a fresh execution.
- **Deterministic reproducibility**: Given the same session key, lap number,
  and driver code, a telemetry query MUST return identical channel arrays
  across runs (subject to FastF1 cache consistency).

## Quality & Testing Standards

- **pytest as test framework**: All automated tests MUST use pytest with
  standard assertions; no unittest subclasses unless wrapping a third-party
  integration.
- **Real data fixtures**: Test fixtures MUST be derived from real F1 race
  data (official results, FastF1 cached sessions). Synthetic/mock data is
  permitted only for unit-testing internal utilities that do not produce
  user-facing numbers.
- **CI gate**: No pull request or feature branch MAY be merged without a
  passing full pytest suite.
- **Regression coverage**: Any bug fix that corrects a numerical output MUST
  include a regression test asserting the corrected value against the
  official ground truth.
- **Edge-case matrix**: The test suite MUST include explicit coverage for:
  - Wet-weather sessions with mixed compounds
  - Red-flagged / suspended races
  - Sprint weekend formats (post-2021 and format revisions)
  - Historical seasons with incomplete data (pre-digital era)
  - Multi-driver team comparisons within a single visualization

## Governance

- This constitution supersedes all other development practices, style guides,
  and ad-hoc conventions for the PitWall AI project.
- Amendments MUST be documented with a version bump, rationale, and migration
  plan for any affected features.
- Every code review MUST include a constitution compliance check: reviewers
  MUST verify that no user-facing number is produced without a traceable
  SQL or Python computation path.
- Complexity in architecture or UI MUST be justified against these principles;
  if a simpler approach satisfies the constitution, it MUST be preferred.
- Runtime development guidance is maintained in the project's spec and plan
  documents, which MUST remain consistent with this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-11-22 | **Last Amended**: 2026-11-22
