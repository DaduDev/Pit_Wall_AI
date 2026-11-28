import json
import os
from pathlib import Path
from typing import List, Optional

# Suppress remote model cost map download in litellm
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

# Base project directory (f1-race-engineer root)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    # Environment & Server
    PROJECT_NAME: str = "PitWall AI"
    APP_ENV: str = Field(default="local")  # "local" | "production"
    ENABLE_OLLAMA_FALLBACK: Optional[bool] = Field(default=None)
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    # Cloud Caching & Rate Limiting
    CACHE_DIR: str = Field(default="")
    REDIS_URL: Optional[str] = Field(default=None)
    RATE_LIMIT_PER_MIN: int = Field(default=15)

    # LLM Settings (ADK Orchestrator & 4-Tier Cascading Failover Client)
    GOOGLE_API_KEY: str = Field(default="")
    GEMINI_API_KEY: str = Field(default="")
    GOOGLE_GENAI_USE_VERTEXAI: bool = Field(default=False)
    GOOGLE_CLOUD_PROJECT: str = Field(default="")
    GOOGLE_CLOUD_LOCATION: str = Field(default="us-central1")
    LLM_PROVIDER: str = Field(default="gemini")  # "gemini" or "ollama"
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_THINKING_LEVEL: str = "low"  # "low" or "medium"

    # Tier 2: Groq OpenAI-Compatible Cloud Fallback
    GROQ_API_KEY: Optional[str] = Field(default=None)
    GROQ_BASE_URL: str = Field(default="https://api.groq.com/openai/v1")
    GROQ_MODEL: str = Field(default="openai/gpt-oss-120b")

    # Tier 3: OpenRouter OpenAI-Compatible Cloud Fallback
    OPENROUTER_API_KEY: Optional[str] = Field(default=None)
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1")
    OPENROUTER_MODEL: str = Field(default="openrouter/free")
    OPENROUTER_HTTP_REFERER: Optional[str] = Field(default=None)

    # Tier 4: Local Ollama Offline Fallback
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

    @model_validator(mode="after")
    def _resolve_runtime_defaults(self) -> "Settings":
        env_norm = (self.APP_ENV or "local").strip().lower()
        if self.ENABLE_OLLAMA_FALLBACK is None:
            self.ENABLE_OLLAMA_FALLBACK = env_norm != "production"
        if not (self.CACHE_DIR or "").strip():
            self.CACHE_DIR = "/tmp/pitwall_cache" if env_norm == "production" else "./data"
        return self

    def get_cors_origins(self) -> List[str]:
        """Parse comma-separated or JSON-array CORS_ORIGINS into a clean list of origins."""
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw:
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(o).strip() for o in parsed if str(o).strip()]
            except Exception:
                pass
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    def get_cache_root(self) -> Path:
        """Return configured writable runtime cache directory."""
        raw = os.environ.get("CACHE_DIR") or self.CACHE_DIR
        if not (raw or "").strip():
            env_norm = (os.environ.get("APP_ENV") or self.APP_ENV or "local").strip().lower()
            raw = "/tmp/pitwall_cache" if env_norm == "production" else "./data"
        return Path(raw)

    def get_fastf1_cache_dir(self) -> Path:
        """Return writable runtime FastF1 cache directory ({CACHE_DIR}/fastf1)."""
        return self.get_cache_root() / "fastf1"

    def get_research_runtime_cache_dir(self) -> Path:
        """Return writable runtime research cache directory ({CACHE_DIR}/research_cache)."""
        return self.get_cache_root() / "research_cache"

    def get_artifact_cache_dir(self) -> Path:
        """Return writable runtime ArtifactStore directory ({CACHE_DIR}/artifacts)."""
        return self.get_cache_root() / "artifacts"


settings = Settings()

# Best-effort directory creation (never crash on read-only containers)
for _dir in (
    settings.DATA_DIR,
    settings.FASTF1_CACHE_DIR,
    settings.OPENF1_CACHE_DIR,
    settings.RESEARCH_CACHE_DIR,
    settings.get_cache_root(),
    settings.get_fastf1_cache_dir(),
    settings.get_research_runtime_cache_dir(),
    settings.get_artifact_cache_dir(),
):
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


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
