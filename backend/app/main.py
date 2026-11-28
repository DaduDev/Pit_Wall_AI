"""
Main FastAPI Application for PitWall AI Race Engineer.
"""

from contextlib import asynccontextmanager
import logging
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.auth.router import router as auth_router
from backend.app.chat.router import router as chat_router
from backend.app.a2a.registry import router as a2a_router
from backend.app.data.duckdb_manager import get_duckdb_manager
from backend.app.data.fastf1_cache import configure_headless_fastf1, init_fastf1_cache
from backend.app.llm import (
    get_gemini_config,
    get_groq_config,
    get_openrouter_config,
    is_ollama_fallback_enabled,
)

# Ensure FastF1 runs in 100% headless mode without interactive terminal prompts
configure_headless_fastf1()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pitwall.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle manager.
    Initializes DuckDB and ingests CSV data if needed, creates curated views,
    and configures FastF1 cache directory.
    """
    logger.info("Starting up PitWall AI backend (env=%s)...", settings.APP_ENV)

    # 1. Initialize FastF1 runtime cache cleanly
    init_fastf1_cache(settings.get_fastf1_cache_dir())

    # 2. Initialize DuckDB & Ingest Data if empty
    db_mgr = get_duckdb_manager()
    try:
        conn = db_mgr.get_connection()
        res = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'results'").fetchone()
        if res and res[0] == 0:
            logger.info("Ingesting Kaggle F1 CSVs into DuckDB...")
            ingested = db_mgr.ingest_all_csvs()
            logger.info(f"Ingested {len(ingested)} tables successfully.")
            views = db_mgr.create_views()
            logger.info(f"Verified {len(views)} curated SQL views.")
        else:
            logger.info("Verified DuckDB tables and curated SQL views ready in read-only mode.")
    except Exception as e:
        logger.warning(f"DuckDB automatic startup ingestion notice: {e}")

    yield

    logger.info("Shutting down PitWall AI backend...")
    db_mgr.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Formula 1 AI Race Engineer with Zero-Hallucination telemetry and historical statistics.",
    version="0.1.0",
    lifespan=lifespan,
)

# Dynamic CORS configuration from comma-separated CORS_ORIGINS setting
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(a2a_router)


def _get_active_providers() -> List[str]:
    """List currently enabled/configured LLM cascade tiers."""
    providers: List[str] = []
    gem_cfg = get_gemini_config()
    if gem_cfg["provider_mode"] != "ollama" and (gem_cfg["use_vertex"] or gem_cfg["api_key"]):
        providers.append("gemini")
    if get_groq_config().get("api_key"):
        providers.append("groq")
    if get_openrouter_config().get("api_key"):
        providers.append("openrouter")
    if is_ollama_fallback_enabled():
        providers.append("ollama")
    return providers


def _build_health_payload() -> dict:
    db_ok = False
    try:
        conn = get_duckdb_manager().get_connection()
        conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    fastf1_dir = str(settings.get_fastf1_cache_dir())
    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "duckdb_ready": db_ok,
        "fastf1_cache_dir": fastf1_dir,
        "active_providers": _get_active_providers(),
        # Backward-compatible aliases
        "project": settings.PROJECT_NAME,
        "database": "connected" if db_ok else "disconnected",
        "fastf1_cache": fastf1_dir,
        "llm_provider": settings.LLM_PROVIDER,
    }

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {
        "status": "ok",
        "service": "PitWall AI",
        "health": "/health",
        "docs": "/docs",
    }

@app.get("/health", tags=["Health"])
async def root_health_check():
    """Primary container readiness & health check endpoint (HTTP 200)."""
    return _build_health_payload()


@app.get("/api/health", tags=["Health"])
async def health_check():
    """API health check endpoint confirming service status and database connectivity."""
    return _build_health_payload()
