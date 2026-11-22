"""
FastF1 Cache & Session Loader for PitWall AI.
Configures disk caching at ./data/fastf1_cache and implements cache-first
lookup with retry logic on transient timeouts.
"""

import logging
import time
from pathlib import Path
from typing import Optional
import fastf1
from backend.app.config import settings

logger = logging.getLogger(__name__)


def init_fastf1_cache(cache_dir: Optional[Path] = None) -> Path:
    """
    Enables and configures FastF1 persistent disk cache.
    """
    target_dir = cache_dir or settings.FASTF1_CACHE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(target_dir))
    logger.info(f"FastF1 cache enabled at {target_dir}")
    return target_dir


def load_session_with_retry(
    year: int,
    gp: str,
    session_type: str = "Q",
    max_retries: int = 2,
    backoff_delay: float = 1.0,
    laps: bool = True,
    telemetry: bool = True,
    weather: bool = False,
    messages: bool = False,
):
    """
    Loads a FastF1 session with cache-first lookup and exponential backoff retry
    on transient network or timeout failures.
    
    Session types: 'FP1', 'FP2', 'FP3', 'Q', 'SQ', 'R'
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
        f"Failed to load FastF1 session for {year} {gp} '{session_type}' after {max_retries + 1} attempts: {last_exception}"
    ) from last_exception
