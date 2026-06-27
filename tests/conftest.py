"""
Shared pytest fixtures: deterministic synthetic price history (no network).

`make_history` builds a dict of ticker -> DataFrame where each ticker follows a
constant compound growth rate, so we can construct any regime we want and assert
the engine classifies it correctly.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
import pytest


def _series_with_total_return(total_return: float, n: int = 120) -> pd.DataFrame:
    """
    Build an OHLCV frame whose Close rises by `total_return` over `n` bars.

    Args:
        total_return: Fractional total return (0.10 == +10% start to end).
        n: Number of daily bars.

    Returns:
        DataFrame with a 'Close' column and a daily DatetimeIndex.
    """
    start = 100.0
    end = start * (1.0 + total_return)
    close = np.linspace(start, end, n)
    idx = pd.date_range(end="2026-06-26", periods=n, freq="D")
    return pd.DataFrame({"Close": close}, index=idx)


def _noisy_series_with_total_return(
    total_return: float, n: int = 120, vol: float = 0.0, seed: int = 0
) -> pd.DataFrame:
    """
    Like `_series_with_total_return` but adds daily noise of std `vol`.

    A non-zero `vol` makes realized volatility meaningful — useful for testing
    that a *volatile* downtrend (a real crash) reads as fear, not just a smooth
    linear decline (which has ~zero realized vol).
    """
    start = 100.0
    drift = (1.0 + total_return) ** (1.0 / max(1, n - 1)) - 1.0
    rng = np.random.default_rng(seed)
    steps = drift + rng.normal(0.0, vol, n - 1)
    close = start * np.cumprod(np.concatenate([[1.0], 1.0 + steps]))
    idx = pd.date_range(end="2026-06-26", periods=n, freq="D")
    return pd.DataFrame({"Close": close}, index=idx)


@pytest.fixture
def make_history():
    """Return a factory: {ticker: total_return} -> {ticker: DataFrame}."""
    def _make(returns: Dict[str, float], n: int = 120) -> Dict[str, pd.DataFrame]:
        return {t: _series_with_total_return(r, n) for t, r in returns.items()}
    return _make


@pytest.fixture
def make_noisy_history():
    """Return a factory that adds volatility: ({ticker: ret}, vol) -> history."""
    def _make(
        returns: Dict[str, float], vol: float = 0.02, n: int = 120
    ) -> Dict[str, pd.DataFrame]:
        return {
            t: _noisy_series_with_total_return(r, n=n, vol=vol, seed=i)
            for i, (t, r) in enumerate(returns.items())
        }
    return _make
