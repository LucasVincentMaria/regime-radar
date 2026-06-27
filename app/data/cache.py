"""
Parquet disk cache for price history.

Mirrors the efficient disk-caching pattern used elsewhere in the developer's
projects: write fetched frames to Parquet, and serve from disk when fresh enough
(within CACHE_TTL_SECONDS) to avoid hammering the data source.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

import pandas as pd

import config
from app.utils import logger


def _safe_filename(ticker: str, period: str, interval: str) -> str:
    """Build a filesystem-safe cache filename for a (ticker, period, interval)."""
    raw = f"{ticker}_{period}_{interval}"
    safe = re.sub(r"[^A-Za-z0-9_.\-]", "_", raw)
    return f"{safe}.parquet"


def _cache_path(ticker: str, period: str, interval: str) -> Path:
    """Return the full cache path for a series, ensuring the dir exists."""
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return config.CACHE_DIR / _safe_filename(ticker, period, interval)


def read_cache(
    ticker: str,
    period: str,
    interval: str,
    ttl_seconds: Optional[int] = None,
) -> Optional[pd.DataFrame]:
    """
    Return cached history if present and fresh, else None.

    Args:
        ticker: Symbol.
        period: Lookback window.
        interval: Bar size.
        ttl_seconds: Freshness window. Defaults to config.CACHE_TTL_SECONDS.

    Returns:
        The cached DataFrame, or None if missing/stale/unreadable.
    """
    ttl = config.CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    path = _cache_path(ticker, period, interval)
    if not path.exists():
        return None

    age = time.time() - path.stat().st_mtime
    if age > ttl:
        return None

    try:
        return pd.read_parquet(path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to read cache {path.name}: {e}")
        return None


def write_cache(
    ticker: str,
    period: str,
    interval: str,
    df: pd.DataFrame,
) -> None:
    """
    Persist a history frame to the Parquet cache.

    Args:
        ticker: Symbol.
        period: Lookback window.
        interval: Bar size.
        df: The DataFrame to store.
    """
    path = _cache_path(ticker, period, interval)
    try:
        df.to_parquet(path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to write cache {path.name}: {e}")
