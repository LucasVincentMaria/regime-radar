"""
Keyless yfinance data source (the v1 provider).

Implements the DataSource interface using yfinance — 100% free, no API key.
All responses are validated before use (per project guidelines: never assume an
API response has the expected fields).
"""

from __future__ import annotations

import warnings
from typing import Dict, List, Optional

import pandas as pd

from app.data.sources.base import DataSource
from app.utils import logger, to_float

# yfinance internally constructs empty Series without a dtype, which pandas
# warns about. It's noise from a dependency, not our code — silence it.
warnings.filterwarnings(
    "ignore",
    message="The default dtype for empty Series",
    category=FutureWarning,
)


class YFinanceSource(DataSource):
    """Free, keyless market data via yfinance."""

    name = "yfinance"
    requires_key = False

    def get_history(
        self,
        ticker: str,
        period: str,
        interval: str,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV history for one ticker via yfinance.

        Args:
            ticker: Symbol (e.g. "SPY", "GC=F").
            period: Lookback window (e.g. "3mo").
            interval: Bar size (e.g. "1d", "5m").

        Returns:
            DataFrame with a 'Close' column indexed by timestamp, or None.
        """
        try:
            import yfinance as yf

            df = yf.download(
                tickers=ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                threads=False,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"yfinance history failed for {ticker}: {e}", exc_info=True)
            return None

        if df is None or df.empty:
            logger.warning(f"yfinance returned no data for {ticker} ({period}/{interval})")
            return None

        # yfinance returns a MultiIndex column frame for single tickers in some
        # versions; flatten it so downstream code can rely on a flat 'Close'.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if "Close" not in df.columns:
            logger.warning(f"No 'Close' column for {ticker}: cols={list(df.columns)}")
            return None

        return df.dropna(subset=["Close"])

    def get_quotes(self, tickers: List[str]) -> Dict[str, float]:
        """
        Fetch the latest price for several tickers (fast live layer).

        Uses a single batched download of recent 1-minute bars and takes the
        last close for each. Tickers with no data are omitted from the result.

        Args:
            tickers: Symbols to quote.

        Returns:
            Mapping of ticker -> last price.
        """
        if not tickers:
            return {}

        try:
            import yfinance as yf

            df = yf.download(
                tickers=tickers,
                period="1d",
                interval="1m",
                progress=False,
                auto_adjust=True,
                threads=False,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"yfinance quotes failed: {e}", exc_info=True)
            return {}

        if df is None or df.empty:
            logger.warning("yfinance returned no quote data")
            return {}

        return self._extract_last_closes(df, tickers)

    @staticmethod
    def _extract_last_closes(df: pd.DataFrame, tickers: List[str]) -> Dict[str, float]:
        """
        Pull the last valid close per ticker from a (possibly MultiIndex) frame.

        Args:
            df: yfinance download result.
            tickers: The tickers requested (drives single-vs-multi handling).

        Returns:
            ticker -> last price for every ticker with valid data.
        """
        quotes: Dict[str, float] = {}

        # Single ticker -> flat columns; multiple -> MultiIndex (field, ticker).
        if len(tickers) == 1:
            ticker = tickers[0]
            if "Close" in df.columns:
                price = to_float(df["Close"].dropna().iloc[-1]) if not df["Close"].dropna().empty else None
                if price is not None:
                    quotes[ticker] = price
            return quotes

        if not isinstance(df.columns, pd.MultiIndex):
            return quotes

        for ticker in tickers:
            try:
                series = df["Close"][ticker].dropna()
            except (KeyError, TypeError):
                continue
            if series.empty:
                continue
            price = to_float(series.iloc[-1])
            if price is not None:
                quotes[ticker] = price

        return quotes
