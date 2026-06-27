"""
Background jobs.

Two cadences:
  - Slow regime refresh (every SLOW_REFRESH_MINUTES): recompute all timeframes,
    update shared state, and persist to SQLite. The dashboard reads state, so
    page loads are instant and rate-limit safe.
  - Live poll (every LIVE_POLL_SECONDS, market hours only): fetch headline quotes
    and push them to connected WebSocket clients.

Every job is wrapped in try/except so one failed fetch never kills the scheduler
(the graceful-recovery pattern from the developer's other bots).
"""

from __future__ import annotations

from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from app.data import storage
from app.data.fetcher import Fetcher
from app.engine.history_series import compute_weekly_history
from app.engine.timeframes import compute_all_timeframes
from app.state import state
from app.utils import is_market_open, logger


async def refresh_regime(fetcher: Fetcher, use_cache: bool = True) -> None:
    """
    Recompute all timeframes + the weekly history, update state, persist to DB.

    Args:
        fetcher: The data fetcher.
        use_cache: Whether to use the Parquet cache (False forces fresh fetch).
    """
    try:
        snapshots = await compute_all_timeframes(fetcher, use_cache=use_cache)
        if not snapshots:
            logger.warning("Regime refresh produced no snapshots")
            return

        state.set_snapshots(snapshots)
        _persist_snapshots(snapshots)
        logger.info(f"Regime refreshed for {len(snapshots)} timeframe(s)")
    except Exception as e:  # noqa: BLE001 — keep the scheduler alive
        logger.error(f"refresh_regime failed: {e}", exc_info=True)

    # Warm the weekly-history cache for the default timeframe so the first chart
    # load is instant. Other timeframes compute on demand (also cached). Its own
    # try/except so a failure here can't affect the regime refresh above.
    try:
        await compute_weekly_history(fetcher, timeframe=config.DEFAULT_TIMEFRAME,
                                     use_cache=use_cache)
    except Exception as e:  # noqa: BLE001 — keep the scheduler alive
        logger.error(f"weekly history warm-up failed: {e}", exc_info=True)


def _persist_snapshots(snapshots: dict) -> None:
    """Write each timeframe's regime + the default timeframe's F&G to SQLite."""
    for timeframe, snap in snapshots.items():
        regime = snap.get("regime")
        if regime:
            storage.save_regime(
                timeframe=timeframe,
                quadrant=regime["quadrant"],
                growth=regime["growth"],
                inflation=regime["inflation"],
                confidence=regime["confidence"],
                detail=regime,
            )

    # Persist Fear & Greed once, from the default timeframe (a stable cadence).
    default_snap = snapshots.get(config.DEFAULT_TIMEFRAME) or next(iter(snapshots.values()))
    for fg in (default_snap.get("feargreed") or {}).values():
        storage.save_feargreed(
            area=fg["area"], score=fg["score"], label=fg["label"]
        )


async def poll_live_quotes(fetcher: Fetcher, broadcaster) -> None:
    """
    Fetch headline quotes during market hours and broadcast them.

    Skips work entirely when the market is closed, so we don't hammer the data
    source overnight.

    Args:
        fetcher: The data fetcher.
        broadcaster: An async callable taking a dict payload to push to clients.
    """
    try:
        if not is_market_open():
            return
        quotes = await fetcher.fetch_quotes(config.LIVE_ASSETS)
        if not quotes:
            return
        state.set_quotes(quotes)
        await broadcaster({
            "type": "quotes",
            "quotes": quotes,
            "ts": state.last_quote_update,
        })
    except Exception as e:  # noqa: BLE001 — keep the scheduler alive
        logger.error(f"poll_live_quotes failed: {e}", exc_info=True)


def build_scheduler(fetcher: Fetcher, broadcaster) -> AsyncIOScheduler:
    """
    Create and configure the AsyncIO scheduler with both jobs.

    Args:
        fetcher: The shared data fetcher.
        broadcaster: Async callable to push live payloads to WebSocket clients.

    Returns:
        A configured (but not yet started) AsyncIOScheduler.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        refresh_regime,
        trigger="interval",
        minutes=config.SLOW_REFRESH_MINUTES,
        args=[fetcher],
        id="regime_refresh",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        poll_live_quotes,
        trigger="interval",
        seconds=config.LIVE_POLL_SECONDS,
        args=[fetcher, broadcaster],
        id="live_poll",
        max_instances=1,
        coalesce=True,
    )

    return scheduler
