"""Unit tests for the indicator helpers (pure functions, no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.engine import indicators as ind


def test_pct_return_basic():
    s = pd.Series([100.0, 110.0])
    assert ind.pct_return(s) == pytest.approx(0.1)


def test_pct_return_too_short():
    assert ind.pct_return(pd.Series([100.0])) is None


def test_pct_return_handles_nan():
    s = pd.Series([100.0, np.nan, 120.0])
    assert ind.pct_return(s) == pytest.approx(0.2)


def test_above_ma_fraction_positive_when_rising():
    s = pd.Series(np.linspace(100, 130, 60))  # steadily rising -> above its MA
    frac = ind.above_ma_fraction(s, period=20)
    assert frac is not None and frac > 0


def test_relative_strength_sign():
    strong = pd.Series([100.0, 120.0])  # +20%
    weak = pd.Series([100.0, 105.0])    # +5%
    rs = ind.relative_strength(strong, weak)
    assert rs is not None and rs > 0


def test_squash_bounds_and_sign():
    assert -1.0 < ind.squash(5.0) <= 1.0
    assert ind.squash(0.0) == 0.0
    assert ind.squash(-5.0) < 0


def test_clamp():
    assert ind.clamp(2.0) == 1.0
    assert ind.clamp(-2.0) == -1.0
    assert ind.clamp(0.5) == 0.5


def test_to_0_100_mapping_and_clamp():
    assert ind.to_0_100(0.0, low=0.0, high=10.0) == 0.0
    assert ind.to_0_100(10.0, low=0.0, high=10.0) == 100.0
    assert ind.to_0_100(5.0, low=0.0, high=10.0) == 50.0
    # Inverted range (high < low) supports "lower is greedier" signals.
    assert ind.to_0_100(12.0, low=35.0, high=12.0) == 100.0
    # Out of range clamps.
    assert ind.to_0_100(-5.0, low=0.0, high=10.0) == 0.0


def test_realized_volatility_nonnegative():
    rng = np.random.default_rng(42)
    prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, 100))
    vol = ind.realized_volatility(pd.Series(prices), lookback=20)
    assert vol is not None and vol >= 0
