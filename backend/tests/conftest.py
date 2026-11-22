import os
import pytest
from pathlib import Path
import duckdb
from backend.app.config import settings

@pytest.fixture(scope="session")
def real_kaggle_dir():
    """Returns path to the Kaggle dataset CSV files."""
    return settings.KAGGLE_DATA_DIR

@pytest.fixture(scope="session")
def duckdb_conn():
    """In-memory DuckDB connection with ingested CSVs and views for testing."""
    from backend.app.data.duckdb_manager import DuckDBManager
    manager = DuckDBManager(db_path=":memory:", csv_dir=settings.KAGGLE_DATA_DIR)
    manager.ingest_all_csvs()
    manager.create_views()
    return manager.get_connection()

@pytest.fixture
def auth_header():
    """Generates a valid JWT auth header for test users."""
    from backend.app.auth.dependencies import create_access_token
    token = create_access_token({"sub": "test@pitwall.ai", "user_id": "test_user_1"})
    return {"Authorization": f"Bearer {token}"}
