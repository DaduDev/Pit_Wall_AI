"""
Main FastAPI Application for PitWall AI Race Engineer.
"""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.auth.router import router as auth_router
from backend.app.chat.router import router as chat_router
from backend.app.data.duckdb_manager import get_duckdb_manager
from backend.app.data.fastf1_cache import init_fastf1_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pitwall.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle manager.
    Initializes DuckDB and ingests CSV data if needed, creates curated views,
    and configures FastF1 cache directory.
    """
    logger.info("Starting up PitWall AI backend...")
    
    # 1. Initialize FastF1 cache
    init_fastf1_cache(settings.FASTF1_CACHE_DIR)

    # 2. Initialize DuckDB & Ingest Data
    db_mgr = get_duckdb_manager()
    try:
        # Check if tables already exist
        conn = db_mgr.get_connection()
        res = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'results'").fetchone()
        if res and res[0] == 0:
            logger.info("Ingesting Kaggle F1 CSVs into DuckDB...")
            ingested = db_mgr.ingest_all_csvs()
            logger.info(f"Ingested {len(ingested)} tables successfully.")
        
        # Ensure curated views are created
        views = db_mgr.create_views()
        logger.info(f"Verified {len(views)} curated SQL views.")
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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint confirming service status and database connectivity."""
    db_ok = False
    try:
        conn = get_duckdb_manager().get_connection()
        conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "project": settings.PROJECT_NAME,
        "database": "connected" if db_ok else "disconnected",
        "fastf1_cache": str(settings.FASTF1_CACHE_DIR),
        "llm_provider": settings.LLM_PROVIDER,
    }
