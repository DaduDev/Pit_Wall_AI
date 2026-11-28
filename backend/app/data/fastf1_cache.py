"""
FastF1 Cache & Session Loader for PitWall AI.
Configures runtime disk caching under {CACHE_DIR}/fastf1 safely with try/except fallback,
configures headless non-interactive mode (silencing terminal credential prompts),
and guards concurrent session.load() calls with Semaphore(2) to cap RAM spikes.
"""

import asyncio
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional
import fastf1
from backend.app.config import settings

logger = logging.getLogger(__name__)

# Concurrency guard capping simultaneous FastF1 session.load() calls to prevent RAM spikes
FASTF1_LOAD_ASYNC_SEMAPHORE = asyncio.Semaphore(2)
_FASTF1_LOAD_SYNC_SEMAPHORE = threading.BoundedSemaphore(2)


def configure_headless_fastf1():
    """
    Ensures FastF1 runs in 100% headless non-interactive mode.
    FastF1 v3.4+ prompts interactively via stdin for a Formula 1 account
    if F1_USERNAME and F1_PASSWORD are not set in the environment.
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
    Enables FastF1 persistent disk cache at {CACHE_DIR}/fastf1 safely inside try/except
    so ephemeral or read-only filesystems fall back cleanly without crashing.
    """
    configure_headless_fastf1()
    target_dir = cache_dir or settings.get_fastf1_cache_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            fastf1.Cache.configure(cache_dir=str(target_dir))
        except Exception:
            fastf1.Cache.enable_cache(str(target_dir))
        logger.info(f"FastF1 cache enabled at {target_dir}")
    except Exception as e:
        logger.warning(f"FastF1 disk cache setup skipped ({target_dir}): {e}")
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
    Loads a FastF1 session with cache-first lookup, bounded by Semaphore(2)
    so concurrent requests never spike container RAM.
    """
    init_fastf1_cache()

    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            session = fastf1.get_session(year, gp, session_type)
            with _FASTF1_LOAD_SYNC_SEMAPHORE:
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


async def async_load_session_with_retry(
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
    """Async entrypoint wrapping FastF1 session loading inside asyncio.Semaphore(2)."""
    async with FASTF1_LOAD_ASYNC_SEMAPHORE:
        return await asyncio.to_thread(
            load_session_with_retry,
            year,
            gp,
            session_type,
            max_retries,
            backoff_delay,
            laps,
            telemetry,
            weather,
            messages,
        )
