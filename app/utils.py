"""
Shared helpers — defined once, imported everywhere.

Per project guidelines, utility functions live in a single module rather than
being re-defined per file.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import config

# Cached market calendar instance (created lazily — the import is heavy).
_MARKET_CAL: Any = None


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Configure root logging once and return the project logger.

    Args:
        level: Log level name (e.g. "INFO"). Falls back to config.LOG_LEVEL.

    Returns:
        A configured logger named "regime_radar".
    """
    log_level = (level or config.LOG_LEVEL).upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("regime_radar")


logger = setup_logging()


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Safely convert a value to float, returning `default` on failure.

    Handles None, NaN, strings, and pandas/numpy scalars without raising.

    Args:
        value: The value to convert.
        default: What to return if conversion fails (default None).

    Returns:
        The float value, or `default`.
    """
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    # Reject NaN / inf.
    if result != result or result in (float("inf"), float("-inf")):
        return default
    return result


def _get_market_calendar() -> Any:
    """Lazily build and cache the NYSE market calendar."""
    global _MARKET_CAL
    if _MARKET_CAL is None:
        import pandas_market_calendars as mcal
        _MARKET_CAL = mcal.get_calendar(config.MARKET_CALENDAR)
    return _MARKET_CAL


def is_market_open(now: Optional[datetime] = None) -> bool:
    """
    Return True if the configured market (NYSE) is open right now.

    Holiday- and weekend-aware via pandas-market-calendars. Used to gate the
    live polling layer so we don't hammer the data source when markets are shut.

    Args:
        now: Override the current time (mainly for testing). Defaults to now (UTC).

    Returns:
        True if the market session is currently open.
    """
    import pandas as pd

    ts = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC")
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")

    try:
        cal = _get_market_calendar()
        schedule = cal.schedule(
            start_date=(ts - pd.Timedelta(days=1)).date(),
            end_date=(ts + pd.Timedelta(days=1)).date(),
        )
        if schedule.empty:
            return False
        # Check the timestamp directly against each session's open/close window.
        # (More robust than open_at_time, which raises if ts falls in a gap.)
        for _, row in schedule.iterrows():
            if row["market_open"] <= ts <= row["market_close"]:
                return True
        return False
    except Exception as e:  # noqa: BLE001 — never let a calendar hiccup crash the loop
        logger.warning(f"Market-open check failed, assuming closed: {e}")
        return False
