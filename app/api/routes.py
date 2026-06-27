"""
REST API routes.

All endpoints read from the in-memory `state` (populated by the scheduler), so
they return instantly. The frontend polls these for the regime board, asset
tables, and Fear & Greed gauges; history endpoints back the trend charts.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import config
from app.data import storage
from app.state import state

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    """Liveness probe + last-update timestamps."""
    return {
        "status": "ok",
        "last_updated": state.last_updated,
        "last_quote_update": state.last_quote_update,
        "timeframes": list(config.TIMEFRAMES.keys()),
    }


@router.get("/meta")
def meta() -> dict:
    """Static metadata the frontend needs to render labels and quadrants."""
    return {
        "quadrants": config.QUADRANTS,
        "timeframes": {
            k: v["label"] for k, v in config.TIMEFRAMES.items()
        },
        "default_timeframe": config.DEFAULT_TIMEFRAME,
        "fear_greed_areas": {
            k: v["label"] for k, v in config.FEAR_GREED_AREAS.items()
        },
        "live_assets": config.LIVE_ASSETS,
        "asset_labels": config.ASSET_LABELS,
    }


def _require_timeframe(timeframe: str) -> str:
    """Validate a timeframe key, raising 400 if unknown."""
    if timeframe not in config.TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unknown timeframe '{timeframe}'")
    return timeframe


@router.get("/snapshot")
def snapshot(
    timeframe: str = Query(default=config.DEFAULT_TIMEFRAME)
) -> dict:
    """
    Full snapshot (regime + F&G + asset tables) for one timeframe.

    Returns 503 if the scheduler hasn't computed it yet.
    """
    _require_timeframe(timeframe)
    snap = state.get_snapshot(timeframe)
    if snap is None:
        raise HTTPException(
            status_code=503,
            detail="Snapshot not ready yet — the first refresh is still running.",
        )
    return snap


@router.get("/regime")
def regime(
    timeframe: str = Query(default=config.DEFAULT_TIMEFRAME)
) -> dict:
    """Just the regime result for a timeframe."""
    return {"timeframe": timeframe, "regime": snapshot(timeframe).get("regime")}


@router.get("/feargreed")
def feargreed(
    timeframe: str = Query(default=config.DEFAULT_TIMEFRAME)
) -> dict:
    """Just the Fear & Greed scores for a timeframe."""
    return {"timeframe": timeframe, "feargreed": snapshot(timeframe).get("feargreed")}


@router.get("/quotes")
def quotes() -> dict:
    """Latest live quotes (populated during market hours)."""
    return {"quotes": state.get_quotes(), "ts": state.last_quote_update}


@router.get("/history/regime")
def history_regime(
    timeframe: str = Query(default=config.DEFAULT_TIMEFRAME),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict:
    """Recent regime snapshots (for the trend chart)."""
    _require_timeframe(timeframe)
    return {
        "timeframe": timeframe,
        "history": storage.get_regime_history(timeframe, limit=limit),
    }


@router.get("/history/feargreed")
def history_feargreed(
    area: str = Query(...),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict:
    """Recent Fear & Greed readings for one area."""
    if area not in config.FEAR_GREED_AREAS:
        raise HTTPException(status_code=400, detail=f"Unknown area '{area}'")
    return {
        "area": area,
        "history": storage.get_feargreed_history(area, limit=limit),
    }


@router.get("/history/series")
async def history_series(
    timeframe: str = Query(default=config.DEFAULT_TIMEFRAME)
) -> dict:
    """
    Year-long weekly regime backtest for the history chart.

    The trailing window per week matches the timeframe, so the chart agrees with
    the live board on the same timeframe. Cached per timeframe (hourly), so this
    is cheap after the first call.
    """
    _require_timeframe(timeframe)
    from app.deps import fetcher
    from app.engine.history_series import compute_weekly_history

    history = await compute_weekly_history(fetcher, timeframe=timeframe)
    if history is None:
        raise HTTPException(
            status_code=503,
            detail="Weekly history not ready yet — still computing.",
        )
    return history
