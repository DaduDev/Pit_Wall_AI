import os
from pathlib import Path
from typing import Optional

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

    # LLM Settings (ADK Orchestrator & Unified Failover Client)
    GOOGLE_API_KEY: str = Field(default="")
    GEMINI_API_KEY: str = Field(default="")
    GOOGLE_GENAI_USE_VERTEXAI: bool = Field(default=False)
    GOOGLE_CLOUD_PROJECT: str = Field(default="")
    GOOGLE_CLOUD_LOCATION: str = Field(default="us-central1")
    LLM_PROVIDER: str = Field(default="gemini")  # "gemini" or "ollama"
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_THINKING_LEVEL: str = "low"  # "low" or "medium"
    OLLAMA_MODEL: str = Field(default="qwen3.5:4b")
    OLLAMA_API_BASE: str = Field(default="http://127.0.0.1:11434")
    OLLAMA_BASE_URL: str = Field(default="http://127.0.0.1:11434/api/chat")
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
    OPENF1_BASE_URL: str = "https://api.openf1.org/v1"
    OPENF1_CACHE_DIR: Path = ROOT_DIR / "data" / "openf1_cache"
    RESEARCH_CACHE_DIR: Path = ROOT_DIR / "data" / "research_cache"
    CORNER_NICKNAMES_PATH: Path = ROOT_DIR / "data" / "corner_nicknames.json"


settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
settings.OPENF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
settings.RESEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def build_thinking_config(model_name: str, preferred_level: Optional[str] = None):
    """
    Construct the lowest-latency supported ThinkingConfig for the given Gemini model.
    - Gemini 2.5 Flash models: thinking_budget=0 (disables thinking delay)
    - Flash-Lite Gemini 3+ models: thinking_level='minimal' by default (~1s SQL/narration)
    - Other Gemini 3+ models: thinking_level=settings.GEMINI_THINKING_LEVEL ('low')
    Returns None if types.ThinkingConfig cannot be constructed.
    """
    try:
        from google.genai import types
        m_lower = (model_name or "").lower()
        if "2.5" in m_lower:
            return types.ThinkingConfig(thinking_budget=0)
        if preferred_level:
            level = preferred_level.lower()
        elif "flash-lite" in m_lower:
            level = "minimal"
        else:
            level = (settings.GEMINI_THINKING_LEVEL or "low").lower()
        return types.ThinkingConfig(thinking_level=level)
    except Exception:
        return None


def is_unsupported_thinking_error(exc: Exception) -> bool:
    """Return True if a Gemini API error indicates thinking_config is unsupported on the model."""
    msg = str(exc).lower()
    return (
        "thinking" in msg
        or "thinking_budget" in msg
        or "thinking_level" in msg
        or "invalid_argument" in msg
    )
