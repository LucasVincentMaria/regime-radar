"""
SQLite storage for regime snapshots and Fear & Greed history.

Two small time-series tables. We store the computed result of each slow refresh
so the dashboard loads instantly and can chart how the regime / sentiment have
evolved. Price history itself lives in the Parquet cache, not here.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

import config
from app.utils import logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS regime_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,           -- ISO-8601 UTC
    timeframe   TEXT    NOT NULL,           -- e.g. "3mo"
    quadrant    TEXT    NOT NULL,           -- RECOVERY / OVERHEAT / ...
    growth      REAL    NOT NULL,           -- growth-axis score (-1..1)
    inflation   REAL    NOT NULL,           -- inflation-axis score (-1..1)
    confidence  REAL    NOT NULL,           -- 0..1
    detail_json TEXT                        -- full snapshot payload
);
CREATE INDEX IF NOT EXISTS idx_regime_tf_ts ON regime_history (timeframe, ts);

CREATE TABLE IF NOT EXISTS feargreed_history (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT    NOT NULL,                -- ISO-8601 UTC
    area   TEXT    NOT NULL,                -- stocks / commodities / bonds / crypto
    score  REAL    NOT NULL,                -- 0..100
    label  TEXT    NOT NULL                 -- "Extreme Fear" ... "Extreme Greed"
);
CREATE INDEX IF NOT EXISTS idx_fg_area_ts ON feargreed_history (area, ts);
"""


def _utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with row access by name, committing on exit."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes if they don't already exist."""
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
        logger.info(f"SQLite ready at {config.DB_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Failed to init DB: {e}", exc_info=True)
        raise


def save_regime(
    timeframe: str,
    quadrant: str,
    growth: float,
    inflation: float,
    confidence: float,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Persist one regime snapshot.

    Args:
        timeframe: The timeframe key (e.g. "3mo").
        quadrant: Detected quadrant name.
        growth: Growth-axis score (-1..1).
        inflation: Inflation-axis score (-1..1).
        confidence: Confidence 0..1.
        detail: Optional full payload, stored as JSON.
    """
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO regime_history "
                "(ts, timeframe, quadrant, growth, inflation, confidence, detail_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    _utc_now_iso(), timeframe, quadrant,
                    growth, inflation, confidence,
                    json.dumps(detail) if detail is not None else None,
                ),
            )
    except sqlite3.Error as e:
        logger.error(f"Failed to save regime: {e}", exc_info=True)


def save_feargreed(area: str, score: float, label: str) -> None:
    """
    Persist one Fear & Greed reading.

    Args:
        area: One of stocks/commodities/bonds/crypto.
        score: 0..100.
        label: Human label for the score band.
    """
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO feargreed_history (ts, area, score, label) "
                "VALUES (?, ?, ?, ?)",
                (_utc_now_iso(), area, score, label),
            )
    except sqlite3.Error as e:
        logger.error(f"Failed to save fear&greed: {e}", exc_info=True)


def get_latest_regime(timeframe: str) -> Optional[Dict[str, Any]]:
    """
    Return the most recent regime snapshot for a timeframe, or None.

    Args:
        timeframe: The timeframe key.

    Returns:
        A dict of the latest row (detail_json parsed), or None if empty.
    """
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM regime_history WHERE timeframe = ? "
                "ORDER BY ts DESC LIMIT 1",
                (timeframe,),
            ).fetchone()
    except sqlite3.Error as e:
        logger.error(f"Failed to read regime: {e}", exc_info=True)
        return None

    if row is None:
        return None
    result = dict(row)
    if result.get("detail_json"):
        try:
            result["detail"] = json.loads(result["detail_json"])
        except json.JSONDecodeError:
            result["detail"] = None
    result.pop("detail_json", None)
    return result


def get_regime_history(timeframe: str, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Return recent regime snapshots for charting (oldest → newest).

    Args:
        timeframe: The timeframe key.
        limit: Max rows.

    Returns:
        List of row dicts (without the heavy detail_json), oldest first.
    """
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT ts, quadrant, growth, inflation, confidence "
                "FROM regime_history WHERE timeframe = ? ORDER BY ts DESC LIMIT ?",
                (timeframe, limit),
            ).fetchall()
    except sqlite3.Error as e:
        logger.error(f"Failed to read regime history: {e}", exc_info=True)
        return []
    return [dict(r) for r in reversed(rows)]


def get_feargreed_history(area: str, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Return recent Fear & Greed readings for an area (oldest → newest).

    Args:
        area: One of stocks/commodities/bonds/crypto.
        limit: Max rows.

    Returns:
        List of row dicts, oldest first.
    """
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT ts, score, label FROM feargreed_history "
                "WHERE area = ? ORDER BY ts DESC LIMIT ?",
                (area, limit),
            ).fetchall()
    except sqlite3.Error as e:
        logger.error(f"Failed to read fear&greed history: {e}", exc_info=True)
        return []
    return [dict(r) for r in reversed(rows)]
