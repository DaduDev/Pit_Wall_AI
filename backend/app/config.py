import os
from pathlib import Path

# Suppress remote model cost map download in litellm
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base project directory (f1-race-engineer root)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    # Environment & Server
    PROJECT_NAME: str = "PitWall AI"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000"
    ]

    # LLM Settings (ADK Orchestrator)
    GOOGLE_API_KEY: str = Field(default="")
    LLM_PROVIDER: str = Field(default="gemini")  # "gemini" or "ollama"
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_THINKING_LEVEL: str = "low"  # "low" or "medium"
    OLLAMA_MODEL: str = Field(default="qwen3.5:4b")
    OLLAMA_API_BASE: str = Field(default="http://localhost:11434")
    SEMAPHORE_CONCURRENCY: int = 3

    # Authentication & Security
    JWT_SECRET: str = Field(default="pitwall-secret-key-change-in-production-f1-race-engineer")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Data paths (relative to ROOT_DIR or absolute)
    DATA_DIR: Path = ROOT_DIR / "data"
    KAGGLE_DATA_DIR: Path = ROOT_DIR / "data" / "kaggle"
    DUCKDB_PATH: Path = ROOT_DIR / "data" / "f1_data.duckdb"
    FASTF1_CACHE_DIR: Path = ROOT_DIR / "data" / "fastf1_cache"
    CORNER_NICKNAMES_PATH: Path = ROOT_DIR / "data" / "corner_nicknames.json"


settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
