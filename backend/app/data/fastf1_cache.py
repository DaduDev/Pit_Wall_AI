"""
FastF1 Cache & Session Loader for PitWall AI.
Configures disk caching at ./data/fastf1_cache, configures headless non-interactive
mode (silencing terminal credential prompts), and implements cache-first
lookup with retry logic on transient timeouts.
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional
import fastf1
from backend.app.config import settings

logger = logging.getLogger(__name__)


def configure_headless_fastf1():
    """
    Ensures FastF1 runs in 100% headless non-interactive mode.
    FastF1 v3.4+ prompts interactively via stdin for a Formula 1 account
    if F1_USERNAME and F1_PASSWORD are not set in the environment.
    In a web API server (FastAPI/Uvicorn), this blocks the server process.

    If F1_USERNAME and F1_PASSWORD are set in .env / os.environ, FastF1 can authenticate.
    If not, this function suppresses interactive terminal prompts and raises F1AuthError,
    allowing FastF1 to proceed unauthenticated or fall back to cached fixtures without blocking.
    """
    username = os.environ.get("F1_USERNAME")
    password = os.environ.get("F1_PASSWORD")
    if username and password:
        logger.info("F1 account credentials detected in environment.")
        return

    try:
        from fastf1.internals import f1account
        from fastf1.exceptions import F1AuthError

        def _no_interactive_login(*args, **kwargs):
            raise F1AuthError(
                "Interactive F1 sign-in disabled for PitWall AI server. "
                "Set F1_USERNAME and F1_PASSWORD in .env for official F1TV livetiming access."
            )

        f1account._AUTHENTICATORS["password"] = _no_interactive_login
        f1account._AUTHENTICATORS["browser"] = _no_interactive_login

        try:
            from fastf1.internals.f1account import login
            login.default_login = _no_interactive_login
        except Exception:
            pass

        # Also patch token_manager to avoid logging 'Signing in to Formula 1 account...'
        def _no_op_get(force_renew=False, auth_func=None):
            token = f1account.token_manager.get_stored()
            if token is not None and token.is_valid():
                return token
            raise F1AuthError("No F1 account credentials configured in environment.")

        f1account.token_manager.get = _no_op_get
        logger.debug("Configured FastF1 in headless mode (interactive terminal prompts disabled).")
    except Exception as e:
        logger.debug(f"FastF1 headless configuration note: {e}")


def init_fastf1_cache(cache_dir: Optional[Path] = None) -> Path:
    """
    Enables and configures FastF1 persistent disk cache and headless mode.
    """
    configure_headless_fastf1()
    target_dir = cache_dir or settings.FASTF1_CACHE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        fastf1.Cache.configure(cache_dir=str(target_dir))
    except Exception:
        fastf1.Cache.enable_cache(str(target_dir))
    logger.info(f"FastF1 cache enabled at {target_dir}")
    return target_dir


def load_session_with_retry(
    year: int,
    gp: str,
    session_type: str = "Q",
    max_retries: int = 1,
    backoff_delay: float = 0.5,
    laps: bool = True,
    telemetry: bool = True,
    weather: bool = False,
    messages: bool = False,
):
    """
    Loads a FastF1 session with cache-first lookup.
    If FastF1 raises SessionNotAvailableError, DataNotLoadedError, or F1AuthError,
    it breaks immediately without retrying so callers can fall back to verified fixtures.
    """
    init_fastf1_cache()

    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            session = fastf1.get_session(year, gp, session_type)
            session.load(laps=laps, telemetry=telemetry, weather=weather, messages=messages)
            return session
        except Exception as e:
            last_exception = e
            err_name = type(e).__name__
            if "SessionNotAvailable" in err_name or "DataNotLoaded" in err_name or "F1Auth" in err_name:
                logger.warning(
                    f"FastF1 session unavailable for {year} {gp} '{session_type}' ({e}). Bypassing retries to use cached fixtures."
                )
                break

            if attempt < max_retries:
                wait_time = backoff_delay * (2 ** attempt)
                logger.warning(
                    f"FastF1 load attempt {attempt + 1} failed for {year} {gp} {session_type}: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"FastF1 load failed after {max_retries + 1} attempts for {year} {gp} {session_type}: {e}")

    raise RuntimeError(
        f"FastF1 session not available for {year} {gp} '{session_type}': {last_exception}"
    ) from last_exception
