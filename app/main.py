"""
FastAPI application — the dashboard server.

Wires together:
  - REST API routes (/api/*)
  - the live WebSocket (/ws/live)
  - the static frontend (served at /)
  - the background scheduler (slow regime refresh + live polling)

Run with: py scripts/run.py   (or: py -m uvicorn app.main:app)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from app.api.routes import router as api_router
from app.api.websocket import manager
from app.data import storage
from app.deps import fetcher as _fetcher
from app.scheduler.jobs import build_scheduler, refresh_regime
from app.utils import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown: init DB, kick a first refresh, start the scheduler.

    The first refresh runs immediately so the dashboard has data within seconds
    of launch instead of waiting a full interval.
    """
    storage.init_db()
    logger.info("Starting initial regime refresh…")
    await refresh_regime(_fetcher, use_cache=False)

    scheduler = build_scheduler(_fetcher, manager.broadcast)
    scheduler.start()
    logger.info(
        f"Scheduler started "
        f"(regime every {config.SLOW_REFRESH_MINUTES}m, "
        f"live every {config.LIVE_POLL_SECONDS}s)"
    )

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


app = FastAPI(title="Regime Radar", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    """Live-quote WebSocket. Clients receive pushed quote updates."""
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from the client; this keeps the socket
            # open and detects disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"WebSocket error: {e}")
        await manager.disconnect(websocket)


@app.get("/")
def index() -> FileResponse:
    """Serve the dashboard's single-page frontend."""
    return FileResponse(config.FRONTEND_DIR / "index.html")


# Static assets (style.css, app.js). Mounted last so it doesn't shadow routes.
app.mount("/static", StaticFiles(directory=str(config.FRONTEND_DIR)), name="static")
