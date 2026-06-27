"""Unit tests for the Fear & Greed engine on synthetic fixtures."""

from __future__ import annotations

from app.engine import feargreed


def test_score_label_bands():
    assert feargreed.score_label(10) == "Extreme Fear"
    assert feargreed.score_label(35) == "Fear"
    assert feargreed.score_label(50) == "Neutral"
    assert feargreed.score_label(65) == "Greed"
    assert feargreed.score_label(90) == "Extreme Greed"


def test_crypto_greed_when_strong_uptrend(make_history):
    # Strong uptrend in crypto -> high momentum -> greedy score.
    history = make_history({"BTC-USD": 0.40, "ETH-USD": 0.35}, n=120)
    result = feargreed.compute_area_score("crypto", history)
    assert result is not None
    assert result["score"] > 50
    assert result["area"] == "crypto"


def test_crypto_fear_when_volatile_downtrend(make_noisy_history):
    # A real crash is BOTH down AND volatile -> momentum and vol both signal fear.
    history = make_noisy_history({"BTC-USD": -0.30, "ETH-USD": -0.25}, vol=0.04)
    result = feargreed.compute_area_score("crypto", history)
    assert result is not None
    assert result["score"] < 50


def test_stocks_score_uses_multiple_inputs(make_history):
    history = make_history({
        "SPY": 0.12, "TLT": -0.02, "HYG": 0.05, "LQD": 0.01,
        "^VIX": -0.50,  # falling VIX series -> last value low-ish
        "XLK": 0.10, "XLI": 0.08, "XLB": 0.06, "XLF": 0.05, "XLC": 0.04,
        "XLY": 0.09, "XLE": 0.03, "XLP": 0.01, "XLU": 0.0, "XLV": 0.02,
    }, n=120)
    result = feargreed.compute_area_score("stocks", history)
    assert result is not None
    assert 0 <= result["score"] <= 100
    assert result["area"] == "stocks"


def test_compute_all_returns_present_areas(make_history):
    history = make_history({
        "BTC-USD": 0.2, "ETH-USD": 0.1,
        "DBC": 0.05, "CL=F": 0.08, "GC=F": 0.03, "HG=F": 0.04,
        "TLT": 0.02, "IEF": 0.01,
    }, n=120)
    results = feargreed.compute_all(history)
    # crypto, commodities, bonds should compute; stocks lacks SPY -> may be None.
    assert "crypto" in results
    assert "commodities" in results
    for r in results.values():
        assert 0 <= r["score"] <= 100


def test_area_none_when_no_inputs():
    assert feargreed.compute_area_score("crypto", {}) is None
