"""
Year-long weekly regime history (backtest).

Fetches ~1 year of daily prices once, then *replays* the regime engine at weekly
steps: for each anchor date, every ticker is sliced to a trailing window ending
at that date and `compute_regime` is run. This yields a real 52-point history of
growth, inflation, and the quadrant — without waiting for the DB to accumulate.

The result is cached in memory (hourly TTL) because the backtest fetches many
tickers and runs the engine dozens of times.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

import pandas as pd

import config
from app.data.fetcher import Fetcher
from app.engine import regime
from app.engine.timeframes import _all_required_tickers
from app.utils import logger

# In-process cache, keyed by timeframe: timeframe -> {"ts": float, "data": dict}.
_cache: Dict[str, Dict[str, object]] = {}


def _window_days_for(timeframe: str) -> int:
    """Return the trailing-window length (days) for a timeframe."""
    return config.HISTORY_WINDOW_DAYS_BY_TIMEFRAME.get(
        timeframe, config.HISTORY_DEFAULT_WINDOW_DAYS
    )


def _weekly_anchors(index: pd.DatetimeIndex, window_days: int) -> List[pd.Timestamp]:
    """
    Pick weekly anchor dates across the available price index.

    Args:
        index: The (sorted) daily DatetimeIndex of fetched prices.
        window_days: Trailing-window length, so the first anchor leaves room.

    Returns:
        A list of timestamps ~HISTORY_STEP_DAYS apart, oldest → newest, each one
        far enough from the start to have a full trailing window.
    """
    if len(index) == 0:
        return []

    end = index[-1]
    # The grid must leave a full trailing window before the first anchor, AND
    # only span the plotted lookback (we fetch more than that for the window).
    earliest_with_window = index[0] + pd.Timedelta(days=window_days)
    lookback_start = end - pd.Timedelta(days=config.HISTORY_LOOKBACK_DAYS)
    start = max(earliest_with_window, lookback_start)
    if start >= end:
        return []

    # Step BACKWARD from the most recent date so the final anchor is always
    # "now" — this makes the chart's right edge match the live board (which also
    # ends on the latest available date). Using `end` + `periods` anchors the
    # grid on `end` (passing both start and end anchors on `start` instead).
    span_days = (end - start).days
    n_periods = span_days // config.HISTORY_STEP_DAYS + 1
    anchors = pd.date_range(
        end=end, periods=n_periods, freq=f"{config.HISTORY_STEP_DAYS}D"
    )
    # Snap each anchor to the last available trading day at or before it.
    snapped: List[pd.Timestamp] = []
    for a in anchors:
        valid = index[index <= a]
        if len(valid) > 0:
            snapped.append(valid[-1])
    # De-dupe while preserving order.
    return list(dict.fromkeys(snapped))


def _slice_trailing(
    full_history: Dict[str, pd.DataFrame],
    anchor: pd.Timestamp,
    window_days: int,
) -> Dict[str, pd.DataFrame]:
    """
    Slice every ticker to the trailing window ending at `anchor`.

    Args:
        full_history: ticker -> full daily DataFrame.
        anchor: The end date of the window.
        window_days: Trailing-window length in days.

    Returns:
        ticker -> sliced DataFrame covering [anchor - window, anchor].
    """
    window_start = anchor - pd.Timedelta(days=window_days)
    sliced: Dict[str, pd.DataFrame] = {}
    for ticker, df in full_history.items():
        window = df.loc[(df.index > window_start) & (df.index <= anchor)]
        if len(window) >= 2:
            sliced[ticker] = window
    return sliced


async def compute_weekly_history(
    fetcher: Fetcher,
    timeframe: str = config.DEFAULT_TIMEFRAME,
    use_cache: bool = True,
) -> Optional[Dict[str, object]]:
    """
    Build the year-long weekly regime history for a given timeframe.

    The trailing window per weekly point matches the timeframe, so the chart's
    right edge agrees with the live board on the same timeframe.

    Args:
        fetcher: The data fetcher.
        timeframe: A key from config.TIMEFRAMES (sets the trailing window).
        use_cache: Serve the in-process cached result if still fresh.

    Returns:
        A dict with a 'points' list (one per week) and metadata, or None.
        Each point: {date, growth, inflation, quadrant, confidence, color}.
    """
    window_days = _window_days_for(timeframe)
    now = time.time()

    cached = _cache.get(timeframe)
    if use_cache and cached is not None:
        age = now - float(cached["ts"])
        if age < config.HISTORY_CACHE_TTL_SECONDS:
            return cached["data"]  # type: ignore[return-value]

    # Fetch enough DAILY history to cover the plotted year PLUS the longest
    # trailing window (so even a 1-year window yields a full year of points).
    full_history = await fetcher.fetch_many(
        _all_required_tickers(),
        period="2y",
        interval="1d",
        use_cache=use_cache,
    )
    if not full_history:
        logger.warning("Weekly history: no price data fetched")
        return None

    # Use the longest series to define the anchor grid.
    longest = max(full_history.values(), key=len)
    anchors = _weekly_anchors(longest.index, window_days)
    if not anchors:
        logger.warning("Weekly history: not enough data for any anchor")
        return None

    points: List[Dict[str, object]] = []
    for anchor in anchors:
        window_history = _slice_trailing(full_history, anchor, window_days)
        result = regime.compute_regime(window_history)
        if result is None:
            continue
        points.append({
            "date": anchor.date().isoformat(),
            "growth": result["growth"],
            "inflation": result["inflation"],
            "quadrant": result["quadrant"],
            "confidence": result["confidence"],
            "color": result["color"],
        })

    payload = {
        "points": points,
        "count": len(points),
        "timeframe": timeframe,
        "window_days": window_days,
        "step_days": config.HISTORY_STEP_DAYS,
        "lookback_days": config.HISTORY_LOOKBACK_DAYS,
    }
    _cache[timeframe] = {"ts": now, "data": payload}
    logger.info(
        f"Weekly history computed: {len(points)} points "
        f"(timeframe={timeframe}, window={window_days}d)"
    )
    return payload
