"""
Shared in-memory application state.

The scheduler writes the latest computed snapshots here; the API reads from here.
This is the "cache the dashboard reads instantly" layer — protected by a lock so
the slow refresh job and incoming requests never see a half-written snapshot.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, Optional


class AppState:
    """Thread-safe holder for the latest regime/F&G snapshots per timeframe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshots: Dict[str, dict] = {}      # timeframe -> snapshot
        self._quotes: Dict[str, float] = {}        # ticker -> last live price
        self._last_updated: Optional[str] = None
        self._last_quote_update: Optional[str] = None

    def set_snapshots(self, snapshots: Dict[str, dict]) -> None:
        """Replace all timeframe snapshots atomically."""
        with self._lock:
            self._snapshots = snapshots
            self._last_updated = datetime.now(timezone.utc).isoformat()

    def get_snapshot(self, timeframe: str) -> Optional[dict]:
        """Return the snapshot for a timeframe, or None if not yet computed."""
        with self._lock:
            return self._snapshots.get(timeframe)

    def get_all_snapshots(self) -> Dict[str, dict]:
        """Return a shallow copy of all snapshots."""
        with self._lock:
            return dict(self._snapshots)

    @property
    def last_updated(self) -> Optional[str]:
        """ISO timestamp of the last full snapshot refresh."""
        with self._lock:
            return self._last_updated

    def set_quotes(self, quotes: Dict[str, float]) -> None:
        """Replace the latest live quotes atomically."""
        with self._lock:
            self._quotes = quotes
            self._last_quote_update = datetime.now(timezone.utc).isoformat()

    def get_quotes(self) -> Dict[str, float]:
        """Return a copy of the latest live quotes."""
        with self._lock:
            return dict(self._quotes)

    @property
    def last_quote_update(self) -> Optional[str]:
        """ISO timestamp of the last live-quote refresh."""
        with self._lock:
            return self._last_quote_update


# Single shared instance used across the app.
state = AppState()
