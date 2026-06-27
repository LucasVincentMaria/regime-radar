"""
Unit tests for the regime engine on synthetic fixtures.

We construct each of the four quadrants by choosing basket returns that make the
Growth and Inflation axes land in the right corner, then assert classification.
"""

from __future__ import annotations

from app.engine import regime


def test_classify_quadrant_corners():
    assert regime.classify_quadrant(0.5, -0.5) == "RECOVERY"     # growth↑ inflation↓
    assert regime.classify_quadrant(0.5, 0.5) == "OVERHEAT"      # growth↑ inflation↑
    assert regime.classify_quadrant(-0.5, -0.5) == "REFLATION"   # growth↓ inflation↓
    assert regime.classify_quadrant(-0.5, 0.5) == "STAGFLATION"  # growth↓ inflation↑


def test_confidence_scales_with_magnitude():
    assert regime.compute_confidence(0.0, 0.0) == 0.0
    assert regime.compute_confidence(1.0, 1.0) == 1.0
    assert regime.compute_confidence(0.5, 0.5) == 0.5


def _recovery_returns():
    """Cyclicals strong, defensives weak; bonds beat commodities (inflation↓)."""
    return {
        # Growth axis: cyclicals up, defensives down
        "XLY": 0.15, "XLI": 0.12, "XLK": 0.18,
        "XLP": -0.02, "XLU": -0.01, "XLV": 0.0,
        # Credit confirm: risk-on
        "HYG": 0.05, "LQD": 0.01,
        # Inflation axis: beneficiaries weak, bonds strong -> inflation falling
        "XLE": -0.05, "DBC": -0.03, "GC=F": -0.02,
        "TLT": 0.06,
        "CL=F": -0.04,
    }


def test_compute_regime_recovery(make_history):
    history = make_history(_recovery_returns())
    result = regime.compute_regime(history)
    assert result is not None
    assert result["quadrant"] == "RECOVERY"
    assert result["growth"] > 0
    assert result["inflation"] < 0
    assert result["bias"] == "long"
    assert result["favored"] == "STOCKS"


def test_compute_regime_overheat(make_history):
    # Growth up AND inflation up.
    returns = {
        "XLY": 0.12, "XLI": 0.10, "XLK": 0.11,
        "XLP": 0.0, "XLU": -0.01, "XLV": 0.0,
        "HYG": 0.04, "LQD": 0.01,
        "XLE": 0.20, "DBC": 0.15, "GC=F": 0.10,
        "TLT": -0.08,
        "CL=F": 0.25,
    }
    result = regime.compute_regime(make_history(returns))
    assert result is not None
    assert result["quadrant"] == "OVERHEAT"
    assert result["growth"] > 0 and result["inflation"] > 0
    assert result["favored"] == "COMMODITIES"


def test_compute_regime_stagflation(make_history):
    # Growth down, inflation up -> short bias.
    returns = {
        "XLY": -0.10, "XLI": -0.08, "XLK": -0.12,
        "XLP": 0.03, "XLU": 0.04, "XLV": 0.02,
        "HYG": -0.04, "LQD": 0.01,
        "XLE": 0.18, "DBC": 0.14, "GC=F": 0.09,
        "TLT": -0.06,
        "CL=F": 0.22,
    }
    result = regime.compute_regime(make_history(returns))
    assert result is not None
    assert result["quadrant"] == "STAGFLATION"
    assert result["growth"] < 0 and result["inflation"] > 0
    assert result["bias"] == "short"


def test_compute_regime_none_on_missing_data(make_history):
    # Only one ticker -> baskets below coverage threshold -> None.
    history = make_history({"XLY": 0.1})
    assert regime.compute_regime(history) is None
