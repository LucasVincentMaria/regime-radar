"""
Multi-timeframe orchestration.

Ties the data fetcher to the regime and Fear & Greed engines, computing a full
snapshot for each configured timeframe. This is what the scheduler runs and the
API serves.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

import config
from app.data.fetcher import Fetcher
from app.engine import feargreed, regime
from app.engine import indicators as ind
from app.utils import logger


def _all_required_tickers() -> List[str]:
    """Collect the de-duplicated set of tickers every engine input needs."""
    tickers: List[str] = []
    tickers += config.GROWTH_CYCLICALS + config.GROWTH_DEFENSIVES + config.GROWTH_CONFIRM
    tickers += config.INFLATION_BENEFICIARIES + config.INFLATION_DEFLATORS + config.INFLATION_CONFIRM
    for members in config.QUADRANT_ASSETS.values():
        tickers += members
    for cfg in config.FEAR_GREED_AREAS.values():
        tickers += cfg.get("tickers", [])  # type: ignore[arg-type]
        tickers += cfg.get("sector_breadth", [])  # type: ignore[arg-type]
    tickers.append("^VIX")
    return list(dict.fromkeys(tickers))


def _asset_table(
    history: Dict[str, pd.DataFrame],
    tickers: List[str],
) -> List[Dict[str, object]]:
    """
    Build a per-asset performance table for the UI.

    Args:
        history: ticker -> price DataFrame.
        tickers: Which tickers to include.

    Returns:
        List of {ticker, label, last, return_pct} dicts for available tickers.
    """
    rows: List[Dict[str, object]] = []
    for ticker in tickers:
        df = history.get(ticker)
        if df is None or "Close" not in df or df["Close"].dropna().empty:
            continue
        close = df["Close"].dropna()
        ret = ind.pct_return(close)
        rows.append({
            "ticker": ticker,
            "label": config.ASSET_LABELS.get(ticker, ticker),
            "last": round(float(close.iloc[-1]), 2),
            "return_pct": round(ret * 100, 2) if ret is not None else None,
        })
    # Sort best performers first (None returns last).
    rows.sort(key=lambda r: (r["return_pct"] is None, -(r["return_pct"] or 0)))
    return rows


async def compute_timeframe(
    fetcher: Fetcher,
    timeframe: str,
    use_cache: bool = True,
) -> Optional[Dict[str, object]]:
    """
    Compute a full snapshot (regime + F&G + asset tables) for one timeframe.

    Args:
        fetcher: The data fetcher.
        timeframe: A key from config.TIMEFRAMES.
        use_cache: Whether to use the Parquet cache.

    Returns:
        A snapshot dict, or None if data was insufficient.
    """
    tf = config.TIMEFRAMES.get(timeframe)
    if tf is None:
        logger.error(f"Unknown timeframe '{timeframe}'")
        return None

    history = await fetcher.fetch_many(
        _all_required_tickers(),
        period=tf["period"],
        interval=tf["interval"],
        use_cache=use_cache,
    )
    if not history:
        logger.warning(f"No history fetched for timeframe '{timeframe}'")
        return None

    regime_result = regime.compute_regime(history)
    fg_result = feargreed.compute_all(history)

    # Per-quadrant asset performance tables.
    quadrant_tables = {
        name: _asset_table(history, members)
        for name, members in config.QUADRANT_ASSETS.items()
    }

    return {
        "timeframe": timeframe,
        "timeframe_label": tf["label"],
        "regime": regime_result,
        "feargreed": fg_result,
        "assets": quadrant_tables,
    }


async def compute_all_timeframes(
    fetcher: Fetcher,
    use_cache: bool = True,
) -> Dict[str, Dict[str, object]]:
    """
    Compute snapshots for every configured timeframe.

    Args:
        fetcher: The data fetcher.
        use_cache: Whether to use the Parquet cache.

    Returns:
        Mapping timeframe -> snapshot for each timeframe that succeeded.
    """
    out: Dict[str, Dict[str, object]] = {}
    for timeframe in config.TIMEFRAMES:
        try:
            snapshot = await compute_timeframe(fetcher, timeframe, use_cache)
        except Exception as e:  # noqa: BLE001 — one bad timeframe must not kill the rest
            logger.error(f"Failed timeframe '{timeframe}': {e}", exc_info=True)
            continue
        if snapshot is not None:
            out[timeframe] = snapshot
    return out
