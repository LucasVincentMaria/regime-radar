"""
DataSource abstract base class — the key-ready provider interface.

v1 ships a single keyless implementation (yfinance). This ABC exists so a keyed
provider (Alpaca, Polygon, FRED) can be dropped in later WITHOUT touching the
engine or API code: they just implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import pandas as pd


class DataSource(ABC):
    """Abstract market-data provider."""

    #: Human-readable name of the provider (for logging).
    name: str = "abstract"

    #: Whether this source needs an API key. v1 keyless source sets False.
    requires_key: bool = False

    @abstractmethod
    def get_history(
        self,
        ticker: str,
        period: str,
        interval: str,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV history for one ticker.

        Args:
            ticker: The symbol (e.g. "SPY", "GC=F", "BTC-USD").
            period: Lookback window (e.g. "3mo", "1y").
            interval: Bar size (e.g. "1d", "5m").

        Returns:
            A DataFrame indexed by timestamp with at least a 'Close' column,
            or None if the fetch failed or returned no data.
        """
        raise NotImplementedError

    @abstractmethod
    def get_quotes(self, tickers: List[str]) -> Dict[str, float]:
        """
        Fetch the latest price for several tickers (used by the live layer).

        Args:
            tickers: Symbols to quote.

        Returns:
            A mapping of ticker -> last price. Tickers that fail are omitted.
        """
        raise NotImplementedError
