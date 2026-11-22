"""
DuckDB Manager for PitWall AI.
Handles CSV ingestion (converting '\\N' to NULL), read-only SQL guardrail validation,
and query execution with execution time tracking.
"""

import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import duckdb
from backend.app.config import settings
from backend.app.data.views import create_curated_views

# Mutating keywords strictly rejected by the read-only guardrail
FORBIDDEN_SQL_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", 
    "REPLACE", "ATTACH", "DETACH", "COPY", "PRAGMA", "CALL", "EXPORT", 
    "IMPORT", "GRANT", "REVOKE", "SET"
}

# Regex to split on comments and whitespace
COMMENT_REGEX = re.compile(r"(--[^\n]*|\/\*.*?\*\/)", re.DOTALL)


def validate_sql(sql: str) -> None:
    """
    Validates that a SQL query is strictly read-only and safe to execute.
    
    Rules:
    1. Query cannot be empty.
    2. Multiple statements separated by semicolon are prohibited.
    3. Query must start with SELECT or WITH.
    4. Prohibits mutating keywords (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.).
    """
    if not sql or not sql.strip():
        raise ValueError("Query string cannot be empty.")

    # Remove SQL comments
    clean_sql = COMMENT_REGEX.sub("", sql).strip()

    # Reject statement stacking / multiple queries
    statements = [s.strip() for s in clean_sql.split(";") if s.strip()]
    if len(statements) > 1:
        raise ValueError("Multiple SQL statements separated by ';' are strictly prohibited.")

    if not statements:
        raise ValueError("No valid SQL statement found.")

    single_stmt = statements[0]
    tokens = re.findall(r"\b[A-Za-z_]+\b", single_stmt)

    if not tokens:
        raise ValueError("Invalid SQL statement.")

    # Must start with SELECT or WITH
    first_token = tokens[0].upper()
    if first_token not in {"SELECT", "WITH"}:
        raise ValueError(f"Only SELECT or WITH queries are permitted. Found: '{first_token}'.")

    # Check for forbidden keywords anywhere in the token stream
    for token in tokens:
        upper_token = token.upper()
        if upper_token in FORBIDDEN_SQL_KEYWORDS:
            # Special case: 'CREATE' is forbidden, even inside subqueries
            raise ValueError(f"Forbidden mutating keyword detected: '{upper_token}'. Query rejected.")


class DuckDBManager:
    """
    Manages DuckDB database initialization, Kaggle CSV ingestion,
    and safe query execution with read-only guardrails.
    """

    def __init__(self, db_path: Optional[str] = None, csv_dir: Optional[Path] = None):
        self.db_path = db_path if db_path is not None else str(settings.DUCKDB_PATH)
        self.csv_dir = csv_dir or settings.KAGGLE_DATA_DIR
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Returns active DuckDB connection, initializing if necessary."""
        if self._conn is None:
            if self.db_path == ":memory:":
                self._conn = duckdb.connect(":memory:")
            else:
                db_file = Path(self.db_path)
                db_file.parent.mkdir(parents=True, exist_ok=True)
                self._conn = duckdb.connect(str(db_file))
        return self._conn

    def ingest_all_csvs(self, csv_dir: Optional[Path] = None, force_reload: bool = False) -> Dict[str, int]:
        """
        Ingests all CSV files from csv_dir into DuckDB tables.
        Converts '\\N' strings to NULL sentinels automatically during ingestion.
        """
        target_dir = csv_dir or self.csv_dir
        conn = self.get_connection()
        csv_files = list(Path(target_dir).glob("*.csv"))
        
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {target_dir}")

        ingested_tables = {}
        for csv_file in csv_files:
            table_name = csv_file.stem
            normalized_path = str(csv_file).replace("\\", "/")

            if force_reload:
                conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')

            # DuckDB read_csv with nullstr=['\\N', ''] normalizes '\N' to NULL natively
            query = f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" AS 
            SELECT * FROM read_csv('{normalized_path}', header=true, nullstr=['\\N', ''], auto_detect=true);
            """
            conn.execute(query)
            row_count = conn.execute(f'SELECT count(*) FROM "{table_name}"').fetchone()[0]
            ingested_tables[table_name] = row_count

        return ingested_tables

    def create_views(self) -> List[str]:
        """Creates the 5 curated read-only views."""
        conn = self.get_connection()
        return create_curated_views(conn)

    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a SQL query after passing read-only guardrails.
        Returns execution results, column names, row count, and execution time in ms.
        """
        validate_sql(sql)

        conn = self.get_connection()
        start_time = time.perf_counter()

        cursor = conn.execute(sql, params or {})
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Convert rows to list of dictionaries
        data = [dict(zip(columns, row)) for row in rows]

        return {
            "columns": columns,
            "data": data,
            "row_count": len(data),
            "execution_time_ms": round(execution_time_ms, 2),
            "sql": sql,
        }

    def close(self) -> None:
        """Closes active database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# Global singleton instance
_global_duckdb_manager: Optional[DuckDBManager] = None

def get_duckdb_manager() -> DuckDBManager:
    """Returns application-wide singleton DuckDBManager."""
    global _global_duckdb_manager
    if _global_duckdb_manager is None:
        _global_duckdb_manager = DuckDBManager()
    return _global_duckdb_manager
