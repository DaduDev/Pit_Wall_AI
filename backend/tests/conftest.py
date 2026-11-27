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


@pytest.fixture(autouse=True)
def protect_gemini_search_quota(monkeypatch):
    """
    Protect live Gemini Search Grounding quota during pytest runs unless RUN_LIVE_GROUNDING=1.
    Individual tests can still override failover_client._call_gemini_sync via monkeypatch.
    """
    if os.environ.get("RUN_LIVE_GROUNDING") == "1":
        yield
        return

    import backend.app.llm.failover_client as fc

    fc.reset_gemini_cooldown()
    orig_call_gemini_sync = fc._call_gemini_sync

    def _mock_guarded_gemini_sync(
        prompt,
        *,
        system_instruction=None,
        model=None,
        preferred_thinking_level=None,
        use_google_search=False,
        cfg=None,
    ):
        if use_google_search:
            return fc.LLMResult(
                text=(
                    "At Turn 4 on Lap 48 of the 2021 São Paulo Grand Prix, Max Verstappen ran wide defending against Lewis Hamilton.\n"
                    "- Both drivers left the circuit at Turn 4 exit without collision.\n"
                    "- FIA race stewards noted the incident and took no further action.\n"
                    "- Hamilton later passed Verstappen cleanly on Lap 59 to win the race."
                ),
                provider="gemini",
                grounded=True,
                sources=[
                    {
                        "title": "FIA Stewards Decision — 2021 São Paulo Grand Prix",
                        "url": "https://www.fia.com/documents/championships/fia-formula-one-world-championship-14/season/season-2021-1108",
                        "uri": "https://www.fia.com/documents/championships/fia-formula-one-world-championship-14/season/season-2021-1108",
                    }
                ],
                model_used=model or "gemini-3.5-flash-lite",
            )
        return orig_call_gemini_sync(
            prompt,
            system_instruction=system_instruction,
            model=model,
            preferred_thinking_level=preferred_thinking_level,
            use_google_search=use_google_search,
            cfg=cfg,
        )

    monkeypatch.setattr(fc, "_call_gemini_sync", _mock_guarded_gemini_sync)
    yield
