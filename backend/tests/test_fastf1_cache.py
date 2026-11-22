"""
Unit tests for FastF1 Cache initialization and setup.
"""

from pathlib import Path
from backend.app.data.fastf1_cache import init_fastf1_cache
from backend.app.config import settings


def test_init_fastf1_cache(tmp_path):
    """Verifies that init_fastf1_cache initializes the directory properly."""
    custom_cache = tmp_path / "test_fastf1_cache"
    assert not custom_cache.exists()
    
    res = init_fastf1_cache(custom_cache)
    assert res == custom_cache
    assert custom_cache.exists()
    assert custom_cache.is_dir()
