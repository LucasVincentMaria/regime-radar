"""
Regime engine — places the market in the Growth × Inflation 2×2.

The core idea (keyless): infer the two macro axes from *relative sector
performance*.

  Growth axis    = cyclicals (XLY/XLI/XLK) vs defensives (XLP/XLU/XLV),
                   confirmed by copper and credit appetite (HYG vs LQD).
  Inflation axis = inflation beneficiaries (XLE/DBC/Gold) vs long bonds (TLT),
                   confirmed by the oil trend.

Each axis is a score in [-1, 1]. Their signs select the quadrant; their
magnitudes drive a confidence score.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

import config
from app.engine import indicators as ind
from app.utils import logger

# A basket needs at least this fraction of its tickers present to be trusted.
_MIN_BASKET_COVERAGE = 0.5


def _basket_return(
    history: Dict[str, pd.DataFrame],
    tickers: List[str],
) -> Optional[float]:
    """
    Equal-weight average return of the tickers present in `history`.

    Args:
        history: ticker -> price DataFrame (with a 'Close' column).
        tickers: The basket members.

    Returns:
        Mean return across available members, or None if too few are present.
    """
    returns: List[float] = []
    for ticker in tickers:
        df = history.get(ticker)
        if df is None or "Close" not in df:
            continue
        r = ind.pct_return(df["Close"])
        if r is not None:
            returns.append(r)

    if not tickers:
        return None
    coverage = len(returns) / len(tickers)
    if coverage < _MIN_BASKET_COVERAGE or not returns:
        return None
    return sum(returns) / len(returns)


def compute_growth_axis(history: Dict[str, pd.DataFrame]) -> Optional[float]:
    """
    Growth-axis score in [-1, 1]: positive = growth above trend.

    Cyclicals outperforming defensives ⇒ risk-on ⇒ growth. The copper/credit
    confirmation nudges the score.

    Args:
        history: ticker -> price DataFrame.

    Returns:
        Growth score in [-1, 1], or None if inputs are insufficient.
    """
    cyc = _basket_return(history, config.GROWTH_CYCLICALS)
    def_ = _basket_return(history, config.GROWTH_DEFENSIVES)
    if cyc is None or def_ is None:
        return None

    raw = cyc - def_  # cyclicals vs defensives spread
    score = ind.squash(raw, scale=0.1)

    # Confirmation: credit appetite (HYG outperforming LQD = risk-on).
    confirm = _basket_return(history, ["HYG"])
    ig = _basket_return(history, ["LQD"])
    if confirm is not None and ig is not None:
        score += 0.2 * ind.squash(confirm - ig, scale=0.05)

    return ind.clamp(score)


def compute_inflation_axis(history: Dict[str, pd.DataFrame]) -> Optional[float]:
    """
    Inflation-axis score in [-1, 1]: positive = inflation rising.

    Inflation beneficiaries (energy/commodities/gold) outperforming long bonds
    ⇒ inflation rising. Oil trend confirms.

    Args:
        history: ticker -> price DataFrame.

    Returns:
        Inflation score in [-1, 1], or None if inputs are insufficient.
    """
    benef = _basket_return(history, config.INFLATION_BENEFICIARIES)
    bonds = _basket_return(history, config.INFLATION_DEFLATORS)
    if benef is None or bonds is None:
        return None

    raw = benef - bonds
    score = ind.squash(raw, scale=0.1)

    # Confirmation: oil trend.
    oil = _basket_return(history, config.INFLATION_CONFIRM)
    if oil is not None:
        score += 0.2 * ind.squash(oil, scale=0.08)

    return ind.clamp(score)


def classify_quadrant(growth: float, inflation: float) -> str:
    """
    Map (growth, inflation) signs to a quadrant name.

    Args:
        growth: Growth-axis score.
        inflation: Inflation-axis score.

    Returns:
        One of RECOVERY / OVERHEAT / REFLATION / STAGFLATION.
    """
    growth_up = growth >= 0
    inflation_up = inflation >= 0
    if growth_up and not inflation_up:
        return "RECOVERY"
    if growth_up and inflation_up:
        return "OVERHEAT"
    if not growth_up and not inflation_up:
        return "REFLATION"
    return "STAGFLATION"


def compute_confidence(growth: float, inflation: float) -> float:
    """
    Confidence in [0, 1] from how far the axes sit from the origin.

    Both axes strongly signed ⇒ high confidence. Near the origin (ambiguous)
    ⇒ low confidence.

    Args:
        growth: Growth-axis score.
        inflation: Inflation-axis score.

    Returns:
        Confidence in [0, 1].
    """
    magnitude = (abs(growth) + abs(inflation)) / 2.0
    return round(min(1.0, magnitude), 3)


def compute_regime(history: Dict[str, pd.DataFrame]) -> Optional[Dict[str, object]]:
    """
    Full regime computation for one set of price history.

    Args:
        history: ticker -> price DataFrame for the relevant timeframe.

    Returns:
        Dict with quadrant, growth, inflation, confidence, bias, favored — or
        None if the axes can't be computed.
    """
    growth = compute_growth_axis(history)
    inflation = compute_inflation_axis(history)
    if growth is None or inflation is None:
        logger.warning("Cannot compute regime: insufficient basket data")
        return None

    quadrant = classify_quadrant(growth, inflation)
    meta = config.QUADRANTS[quadrant]
    return {
        "quadrant": quadrant,
        "growth": round(growth, 4),
        "inflation": round(inflation, 4),
        "confidence": compute_confidence(growth, inflation),
        "bias": meta["bias"],
        "favored": meta["favored"],
        "color": meta["color"],
    }
