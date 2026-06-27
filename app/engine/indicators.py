"""
Shared technical-analysis helpers.

Pure functions on pandas Series — no I/O, no globals — so they are trivial to
unit-test on fixture data. These are the building blocks the regime and
Fear & Greed engines compose.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


def pct_return(series: pd.Series, lookback: Optional[int] = None) -> Optional[float]:
    """
    Percentage return of a price series over the last `lookback` bars.

    Args:
        series: Price series (e.g. Close).
        lookback: Number of bars back to measure from. None = full series.

    Returns:
        Fractional return (0.05 == +5%), or None if not computable.
    """
    s = series.dropna()
    if len(s) < 2:
        return None
    start = s.iloc[0] if lookback is None else s.iloc[max(0, len(s) - lookback - 1)]
    end = s.iloc[-1]
    if start == 0 or pd.isna(start) or pd.isna(end):
        return None
    return float(end / start - 1.0)


def moving_average(series: pd.Series, period: int) -> pd.Series:
    """
    Simple moving average over `period` bars.

    Args:
        series: Price series.
        period: Window length.

    Returns:
        SMA series (leading values are NaN until the window fills).
    """
    return series.rolling(window=period, min_periods=period).mean()


def above_ma_fraction(series: pd.Series, period: int) -> Optional[float]:
    """
    How far the latest price sits above/below its moving average, normalized.

    Used as a "trend" signal: positive = above trend, negative = below.

    Args:
        series: Price series.
        period: MA lookback.

    Returns:
        (price / ma - 1), or None if the MA can't be computed.
    """
    s = series.dropna()
    if len(s) < period:
        return None
    ma = moving_average(s, period).iloc[-1]
    last = s.iloc[-1]
    if pd.isna(ma) or ma == 0:
        return None
    return float(last / ma - 1.0)


def realized_volatility(series: pd.Series, lookback: int = 20) -> Optional[float]:
    """
    Annualized realized volatility from log returns over `lookback` bars.

    Args:
        series: Price series.
        lookback: Number of bars to use.

    Returns:
        Annualized volatility (e.g. 0.20 == 20%), or None.
    """
    s = series.dropna()
    if len(s) < lookback + 1:
        return None
    log_ret = np.log(s / s.shift(1)).dropna().iloc[-lookback:]
    if log_ret.empty:
        return None
    daily_std = float(log_ret.std())
    return daily_std * math.sqrt(252)


def relative_strength(
    numerator: pd.Series,
    denominator: pd.Series,
    lookback: Optional[int] = None,
) -> Optional[float]:
    """
    Relative performance of one series vs another over a lookback.

    Positive means `numerator` outperformed `denominator`. This is the core
    primitive for the regime axes (cyclicals vs defensives, etc.).

    Args:
        numerator: Price series A.
        denominator: Price series B.
        lookback: Bars to measure over. None = full overlap.

    Returns:
        ret(A) - ret(B), or None if either return is unavailable.
    """
    ret_a = pct_return(numerator, lookback)
    ret_b = pct_return(denominator, lookback)
    if ret_a is None or ret_b is None:
        return None
    return ret_a - ret_b


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    """Clamp a value into [low, high]."""
    return max(low, min(high, value))


def squash(value: float, scale: float = 0.1) -> float:
    """
    Squash an unbounded score into [-1, 1] via tanh.

    `scale` sets how quickly the function saturates: a relative-strength
    difference of `scale` maps to ~0.76. Lets us turn raw return spreads into
    bounded axis scores.

    Args:
        value: Raw score (e.g. a return spread).
        scale: Normalization scale.

    Returns:
        A value in (-1, 1).
    """
    if scale == 0:
        return 0.0
    return float(np.tanh(value / scale))


def to_0_100(value: float, low: float, high: float) -> float:
    """
    Linearly map `value` from [low, high] onto a 0..100 scale, clamped.

    Used to turn raw sentiment inputs into Fear & Greed sub-scores.

    Args:
        value: The raw value.
        low: Value that should map to 0 (extreme fear).
        high: Value that should map to 100 (extreme greed).

    Returns:
        A score in [0, 100].
    """
    if high == low:
        return 50.0
    frac = (value - low) / (high - low)
    return float(max(0.0, min(100.0, frac * 100.0)))
