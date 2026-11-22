# PitWall AI — Antigravity Agent Context & Instructions

Please refer to [AGENTS.md](AGENTS.md) for full project rules, constitution principles, architecture, and feature artifacts.

## Summary Checklist for Agents
- Enforce **Zero-Hallucination Math**: All numbers MUST come from DuckDB SQL or deterministic Python/NumPy calculations.
- Maintain **Data Domain Separation**: DuckDB for historical (1950–2024+); OpenF1 (2023+) / FastF1 for car telemetry.
- Use **Dark HUD Theme**: Background `#0B0F17`, team colors from OpenF1 / FastF1, WCAG AA contrast.
- Always provide **Engineering Trace** metadata (SQL queries, OpenF1 / FastF1 parameters).
- Validate with **Pytest** using real race data fixtures.
