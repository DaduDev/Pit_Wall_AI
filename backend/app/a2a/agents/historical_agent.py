"""
Historical SQL Specialist Agent for PitWall AI (A2A).
Executes read-only DuckDB queries with alias resolution and 1x zero-row retry,
storing full result tables in the shared ArtifactStore and returning compact summaries.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, Optional

from google.adk.agents.llm_agent import LlmAgent
from a2a.types import AgentCard, AgentSkill, AgentInterface

from backend.app.config import settings
from backend.app.a2a.artifact_store import get_artifact_store
from backend.app.data.duckdb_manager import get_duckdb_manager, validate_sql
from backend.app.agent.tools.historical_sql import _attempt_zero_row_correction

logger = logging.getLogger("pitwall.a2a.historical")


class HistoricalSQLAgent:
    """Specialist agent for DuckDB historical analytics (1950–2024+)."""

    def __init__(self, name: str = "historical_agent"):
        self.name = name
        self.db = get_duckdb_manager()
        self.artifact_store = get_artifact_store()
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> LlmAgent:
        """Create ADK LlmAgent wrapper."""
        return LlmAgent(
            name=self.name,
            model="gemini-3.8-flash",
            instruction=(
                "You are the PitWall AI Historical Race Engineer. Query DuckDB historical views "
                "(v_race_results, v_qualifying, v_pit_stops, v_driver_standings, v_constructor_standings) "
                "for Formula 1 statistics from 1950 to 2024+. Never hallucinate statistics."
            ),
            tools=[self.execute_sql],
        )

    def _normalize_common_aliases(self, sql: str) -> str:
        """Normalize common SQL column variations and circuit aliases in queries."""
        normalized = re.sub(r"\bconstructor_name\b", "constructor", sql, flags=re.IGNORECASE)
        normalized = re.sub(r"\bfinishing_position\b", "position", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\brace_year\b", "year", normalized, flags=re.IGNORECASE)

        # Brazil / São Paulo aliases with optional table alias support
        def _build_brazil_predicate(alias: str | None) -> str:
            pfx = f"{alias}." if alias else ""
            return (
                f"(lower({pfx}grand_prix) LIKE '%brazil%' OR "
                f"lower({pfx}grand_prix) LIKE '%são paulo%' OR "
                f"lower({pfx}grand_prix) LIKE '%sao paulo%' OR "
                f"lower({pfx}circuit_country) = 'brazil')"
            )

        pattern_brazil = re.compile(
            r"(?:"
            r"(?:lower\s*\(\s*(?:(?P<a1>\w+)\.)?grand_prix\s*\)|(?:(?P<a2>\w+)\.)?grand_prix)\s+(?:i?like)\s+'%brazil[^']*%'"
            r"|"
            r"(?:lower\s*\(\s*(?:(?P<a3>\w+)\.)?grand_prix\s*\)|(?:(?P<a4>\w+)\.)?grand_prix)\s*=\s*'(?:brazilian|brazil)\s+grand\s+prix'"
            r"|"
            r"(?:lower\s*\(\s*(?:(?P<a5>\w+)\.)?circuit_country\s*\)|(?:(?P<a6>\w+)\.)?circuit_country)\s*=\s*'brazil'"
            r")",
            re.IGNORECASE,
        )
        normalized = pattern_brazil.sub(
            lambda m: _build_brazil_predicate(
                m.group("a1") or m.group("a2") or m.group("a3") or m.group("a4") or m.group("a5") or m.group("a6")
            ),
            normalized,
        )

        return normalized

    def generate_sql_from_question(self, question: str) -> str:
        """
        Generate a read-only DuckDB SQL query from a natural-language question.
        Uses Gemini LLM if available; falls back to deterministic domain template matching.
        """
        api_key = (
            os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or getattr(settings, "GOOGLE_API_KEY", "")
            or getattr(settings, "GEMINI_API_KEY", "")
        )
        if api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                prompt = (
                    "You are a DuckDB SQL generator for Formula 1 historical data. "
                    "Available curated views:\n"
                    "- v_race_results (race_id, driver_id, constructor_id, driver_name, year, round, grand_prix, "
                    "  circuit, circuit_country, driver_code, forename, surname, constructor, grid, position, points, laps, finish_time, finish_ms, status)\n"
                    "- v_qualifying (race_id, driver_id, driver_name, year, round, grand_prix, circuit, circuit_country, driver_code, constructor, position, q1, q2, q3)\n"
                    "- v_pit_stops (race_id, driver_id, driver_name, year, round, grand_prix, circuit, circuit_country, driver_code, surname, constructor, stop, lap, duration, duration_ms)\n"
                    "- v_driver_standings (race_id, driver_id, driver_name, year, round, grand_prix, driver_code, points, position, wins)\n"
                    "- v_constructor_standings (race_id, constructor_id, year, round, grand_prix, constructor, points, position, wins)\n\n"
                    "Rules:\n"
                    "1. For Brazilian Grand Prix (2021+ São Paulo), use (lower(grand_prix) LIKE '%brazil%' OR lower(grand_prix) LIKE '%são paulo%' OR lower(circuit_country) = 'brazil').\n"
                    "2. Always select driver_code, driver_name, constructor, position, year, grand_prix.\n"
                    "3. For race winners, check position = 1.\n"
                    "4. Output ONLY raw SQL starting with SELECT or WITH. No markdown code blocks, no explanations.\n"
                    f"Question: {question}"
                )
                for model_candidate in ["gemini-3.8-flash", "gemini-3.5-flash-lite"]:
                    try:
                        resp = client.models.generate_content(model=model_candidate, contents=prompt)
                        if resp and resp.text:
                            raw_sql = resp.text.strip()
                            raw_sql = re.sub(r"^```(?:sql)?", "", raw_sql, flags=re.IGNORECASE).strip()
                            raw_sql = re.sub(r"```$", "", raw_sql).strip()
                            if raw_sql.lower().startswith(("select", "with")):
                                return raw_sql
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"LLM SQL generation failed: {e}")

        # Deterministic Fallback Rule Engine for Natural Language questions
        q_lower = question.lower()
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", q_lower)
        year = int(year_match.group(1)) if year_match else None

        is_brazil = any(k in q_lower for k in ["brazil", "brazilian", "sao paulo", "são paulo", "interlagos"])
        gp_filter = ""
        if is_brazil:
            gp_filter = "(lower(grand_prix) LIKE '%brazil%' OR lower(grand_prix) LIKE '%são paulo%' OR lower(circuit_country) = 'brazil')"
        elif "monza" in q_lower or "italian" in q_lower or "italy" in q_lower:
            gp_filter = "(lower(grand_prix) LIKE '%italian%' OR lower(grand_prix) LIKE '%monza%')"
        elif "silverstone" in q_lower or "british" in q_lower or "britain" in q_lower:
            gp_filter = "(lower(grand_prix) LIKE '%british%' OR lower(circuit_country) IN ('uk', 'united kingdom'))"
        elif "spa" in q_lower or "belgian" in q_lower or "belgium" in q_lower:
            gp_filter = "(lower(grand_prix) LIKE '%belgian%' OR lower(circuit_country) = 'belgium')"
        elif "monaco" in q_lower:
            gp_filter = "(lower(grand_prix) LIKE '%monaco%')"
        elif "canada" in q_lower or "canadian" in q_lower or "montreal" in q_lower:
            gp_filter = "(lower(grand_prix) LIKE '%canadian%' OR lower(circuit_country) = 'canada')"

        driver_filter = ""
        for code, name in [
            ("HAM", "hamilton"), ("VER", "verstappen"), ("LEC", "leclerc"),
            ("NOR", "norris"), ("PIA", "piastri"), ("RUS", "russell"),
            ("ALO", "alonso"), ("SAI", "sainz"), ("PER", "perez"),
            ("BOT", "bottas"), ("VET", "vettel"), ("MSC", "schumacher"),
            ("SEN", "senna"), ("PRO", "prost")
        ]:
            if name in q_lower or f" {code.lower()} " in f" {q_lower} ":
                driver_filter = f"(driver_code = '{code}' OR lower(driver_name) LIKE '%{name}%')"
                break

        # Winner
        if any(w in q_lower for w in ["who won", "winner", "first place", "victory"]):
            where_clauses = ["position = 1"]
            if year:
                where_clauses.append(f"year = {year}")
            if gp_filter:
                where_clauses.append(gp_filter)
            return f"SELECT year, grand_prix, driver_code, driver_name, constructor, finish_time FROM v_race_results WHERE {' AND '.join(where_clauses)} ORDER BY year DESC, round ASC LIMIT 5"

        # Podium
        if any(w in q_lower for w in ["podium", "top 3", "top three"]):
            where_clauses = ["position <= 3"]
            if year:
                where_clauses.append(f"year = {year}")
            if gp_filter:
                where_clauses.append(gp_filter)
            return f"SELECT year, grand_prix, position, driver_code, driver_name, constructor, points FROM v_race_results WHERE {' AND '.join(where_clauses)} ORDER BY position ASC LIMIT 3"

        # Pole
        if any(w in q_lower for w in ["pole", "qualifying"]):
            where_clauses = ["position = 1"]
            if year:
                where_clauses.append(f"year = {year}")
            if gp_filter:
                where_clauses.append(gp_filter)
            return f"SELECT year, grand_prix, driver_code, driver_name, constructor, q3 FROM v_qualifying WHERE {' AND '.join(where_clauses)} ORDER BY year DESC LIMIT 5"

        # Standings / champion
        if any(w in q_lower for w in ["championship", "standings", "champion", "title"]):
            y = year or 2024
            if "constructor" in q_lower or "team" in q_lower:
                return f"SELECT year, constructor, points, wins, position FROM v_constructor_standings WHERE year = {y} AND round = (SELECT max(round) FROM v_constructor_standings WHERE year = {y}) ORDER BY position ASC LIMIT 10"
            return f"SELECT year, driver_code, driver_name, points, wins, position FROM v_driver_standings WHERE year = {y} AND round = (SELECT max(round) FROM v_driver_standings WHERE year = {y}) ORDER BY position ASC LIMIT 10"

        # Driver results
        if driver_filter:
            where_clauses = [driver_filter]
            if year:
                where_clauses.append(f"year = {year}")
            if gp_filter:
                where_clauses.append(gp_filter)
            return f"SELECT year, grand_prix, position, points, driver_code, constructor FROM v_race_results WHERE {' AND '.join(where_clauses)} ORDER BY year DESC, round DESC LIMIT 10"

        where_clauses = []
        if year:
            where_clauses.append(f"year = {year}")
        if gp_filter:
            where_clauses.append(gp_filter)
        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        return f"SELECT year, grand_prix, position, driver_code, driver_name, constructor, points FROM v_race_results {where_str} ORDER BY year DESC, position ASC LIMIT 10"

    def execute_sql(self, sql: str, chart_title: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a DuckDB SQL query, applying alias self-correction on zero-rows,
        storing the result in ArtifactStore (only if non-empty), and returning compact summary with dataset_id.
        """
        t_start = time.perf_counter()
        clean_sql = self._normalize_common_aliases(sql.strip().rstrip(";"))

        try:
            validate_sql(clean_sql)
            result = self.db.execute_query(clean_sql)
            executed_sql = clean_sql

            # 1x Zero-row retry with alias self-correction
            if result.get("row_count", 0) == 0:
                corrected = _attempt_zero_row_correction(clean_sql)
                if corrected and corrected != clean_sql:
                    try:
                        validate_sql(corrected)
                        corrected_res = self.db.execute_query(corrected)
                        if corrected_res.get("row_count", 0) > 0:
                            result = corrected_res
                            executed_sql = corrected
                            logger.info(f"Zero-row self-correction succeeded: {corrected}")
                    except Exception as err:
                        logger.warning(f"Zero-row correction failed: {err}")

            exec_time = round((time.perf_counter() - t_start) * 1000, 2)
            row_count = result.get("row_count", 0)
            data_rows = result.get("data", [])
            columns = result.get("columns", [])

            # Do NOT store empty 0-row artifacts
            if row_count == 0:
                return {
                    "success": False,
                    "domain": "historical_sql",
                    "dataset_id": None,
                    "row_count": 0,
                    "columns": columns,
                    "summary": f"Query returned 0 rows: {executed_sql}",
                    "sample_rows": [],
                    "trace": {
                        "data_domain": "historical_sql",
                        "sql": executed_sql,
                        "row_count": 0,
                        "execution_time_ms": exec_time,
                        "dataset_id": None,
                    },
                    "error": "Query returned 0 rows",
                }

            # Store the full non-empty result set in ArtifactStore
            dataset_metadata = {
                "domain": "historical_sql",
                "sql": executed_sql,
                "columns": columns,
                "row_count": row_count,
                "chart_title": chart_title,
            }
            dataset_id = self.artifact_store.put(
                data=data_rows,
                metadata=dataset_metadata,
                ttl_seconds=3600,
            )

            # Compact summary string for A2A message exchange
            summary = (
                f"Retrieved {row_count} rows across columns {columns} in {exec_time}ms. "
                f"Dataset stored under dataset_id='{dataset_id}'."
            )

            trace_payload = {
                "data_domain": "historical_sql",
                "sql": executed_sql,
                "row_count": row_count,
                "execution_time_ms": exec_time,
                "dataset_id": dataset_id,
            }

            return {
                "success": True,
                "domain": "historical_sql",
                "dataset_id": dataset_id,
                "row_count": row_count,
                "columns": columns,
                "summary": summary,
                "sample_rows": data_rows[:10],
                "trace": trace_payload,
                "error": None,
            }

        except Exception as e:
            logger.error(f"HistoricalSQLAgent error on query: {sql}. Reason: {e}")
            return {
                "success": False,
                "domain": "historical_sql",
                "dataset_id": None,
                "row_count": 0,
                "columns": [],
                "summary": f"Query execution failed: {e}",
                "sample_rows": [],
                "trace": {
                    "data_domain": "historical_sql",
                    "sql": clean_sql,
                    "error": str(e),
                },
                "error": str(e),
            }

    def query(self, sql_or_query: str, chart_title: Optional[str] = None) -> Dict[str, Any]:
        """Convenience query method for direct agent invocation (accepts SQL or natural language question)."""
        stripped = sql_or_query.strip()
        if stripped.lower().startswith(("select", "with")):
            return self.execute_sql(stripped, chart_title=chart_title)
        
        # Natural language question -> generate SQL
        generated_sql = self.generate_sql_from_question(stripped)
        return self.execute_sql(generated_sql, chart_title=chart_title or stripped)

    @classmethod
    def get_agent_card(cls, base_url: str = "http://localhost:8000/a2a/historical") -> AgentCard:
        """Construct standard A2A AgentCard for HistoricalSQLAgent."""
        return AgentCard(
            name="historical_agent",
            description="Formula 1 Historical Statistics Agent (1950-2024+) powered by DuckDB SQL curated views.",
            version="1.0.0",
            supported_interfaces=[
                AgentInterface(url=base_url, protocol_binding="HTTP_JSON", protocol_version="1.0")
            ],
            skills=[
                AgentSkill(
                    id="execute_sql",
                    name="execute_sql",
                    description="Executes a read-only DuckDB SQL query against historical F1 views (v_race_results, v_qualifying, v_pit_stops, v_driver_standings).",
                    tags=["sql", "duckdb", "historical"],
                )
            ],
        )


_historical_agent_instance: Optional[HistoricalSQLAgent] = None


def get_historical_agent() -> HistoricalSQLAgent:
    """Get singleton HistoricalSQLAgent."""
    global _historical_agent_instance
    if _historical_agent_instance is None:
        _historical_agent_instance = HistoricalSQLAgent()
    return _historical_agent_instance
