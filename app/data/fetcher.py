"""
Async fetch orchestration with rate limiting.

Wraps a DataSource and fetches many tickers concurrently, bounded by an
asyncio.Semaphore (the rate-limiting pattern the developer already uses).
Cache-first: serves fresh Parquet from disk before hitting the network.
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

import pandas as pd

import config
from app.data import cache
from app.data.sources.base import DataSource
from app.data.sources.yfinance_source import YFinanceSource
from app.utils import logger


class Fetcher:
    """Concurrent, cache-first, rate-limited data fetcher."""

    def __init__(
        self,
        source: Optional[DataSource] = None,
        max_concurrent: Optional[int] = None,
    ) -> None:
        """
        Args:
            source: The data provider. Defaults to keyless YFinanceSource.
            max_concurrent: Concurrency cap. Defaults to config value.
        """
        self.source: DataSource = source or YFinanceSource()
        limit = max_concurrent or config.MAX_CONCURRENT_FETCHES
        self._semaphore = asyncio.Semaphore(limit)

    async def _fetch_one(
        self,
        ticker: str,
        period: str,
        interval: str,
        use_cache: bool,
    ) -> Optional[pd.DataFrame]:
        """Fetch one ticker (cache-first), bounded by the semaphore."""
        if use_cache:
            cached = cache.read_cache(ticker, period, interval)
            if cached is not None:
                return cached

        async with self._semaphore:
            # yfinance is sync/blocking → run it off the event loop.
            df = await asyncio.to_thread(
                self.source.get_history, ticker, period, interval
            )

        if df is not None and not df.empty:
            cache.write_cache(ticker, period, interval, df)
        return df

    async def fetch_many(
        self,
        tickers: List[str],
        period: str,
        interval: str,
        use_cache: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch history for many tickers concurrently.

        Args:
            tickers: Symbols to fetch.
            period: Lookback window.
            interval: Bar size.
            use_cache: Serve fresh cache when available (default True).

        Returns:
            Mapping ticker -> DataFrame for every ticker that returned data.
            Failed tickers are simply absent.
        """
        unique = list(dict.fromkeys(tickers))  # de-dupe, preserve order
        tasks = [self._fetch_one(t, period, interval, use_cache) for t in unique]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out: Dict[str, pd.DataFrame] = {}
        for ticker, result in zip(unique, results):
            if isinstance(result, Exception):
                logger.error(f"Fetch error for {ticker}: {result}")
                continue
            if result is not None and not result.empty:
                out[ticker] = result
        return out

    async def fetch_quotes(self, tickers: List[str]) -> Dict[str, float]:
        """
        Fetch latest prices for the live layer (no cache — always fresh).

        Args:
            tickers: Symbols to quote.

        Returns:
            Mapping ticker -> last price.
        """
        async with self._semaphore:
            return await asyncio.to_thread(self.source.get_quotes, tickers)
