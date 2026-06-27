"""
Fear & Greed engine — one composite 0..100 score per asset area.

CNN's index is equities-only and has no free API, so we compute our OWN
transparent composite per area from keyless inputs. Each score blends a few
sentiment sub-signals (momentum, volatility, safe-haven/credit demand) into a
single 0..100 number (0 = extreme fear, 100 = extreme greed).
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

import config
from app.engine import indicators as ind
from app.utils import logger

# Label bands for a 0..100 score.
_BANDS = [
    (0, 25, "Extreme Fear"),
    (25, 45, "Fear"),
    (45, 55, "Neutral"),
    (55, 75, "Greed"),
    (75, 101, "Extreme Greed"),
]


def score_label(score: float) -> str:
    """Return the human label for a 0..100 Fear & Greed score."""
    for low, high, label in _BANDS:
        if low <= score < high:
            return label
    return "Neutral"


def _momentum_score(df: Optional[pd.DataFrame]) -> Optional[float]:
    """0..100 sub-score: price vs its trend MA (greed = above trend)."""
    if df is None or "Close" not in df:
        return None
    above = ind.above_ma_fraction(df["Close"], config.TREND_MA_PERIOD)
    if above is None:
        # Fall back to a shorter window if the series is short.
        above = ind.above_ma_fraction(df["Close"], max(5, len(df["Close"]) // 2))
    if above is None:
        return None
    # +/-10% around trend spans the full fear..greed range.
    return ind.to_0_100(above, low=-0.10, high=0.10)


def _volatility_score(df: Optional[pd.DataFrame]) -> Optional[float]:
    """0..100 sub-score: low vol = greed, high vol = fear (inverted)."""
    if df is None or "Close" not in df:
        return None
    vol = ind.realized_volatility(df["Close"], lookback=20)
    if vol is None:
        return None
    # Higher annualized vol -> more fear. 10% vol = calm, 50% vol = panic.
    return ind.to_0_100(vol, low=0.50, high=0.10)


def _vix_score(history: Dict[str, pd.DataFrame]) -> Optional[float]:
    """0..100 sub-score from the VIX level (low VIX = greed)."""
    df = history.get("^VIX")
    if df is None or "Close" not in df or df["Close"].dropna().empty:
        return None
    vix = float(df["Close"].dropna().iloc[-1])
    # VIX 12 = greed, VIX 35 = fear.
    return ind.to_0_100(vix, low=35.0, high=12.0)


def _safe_haven_score(history: Dict[str, pd.DataFrame]) -> Optional[float]:
    """0..100: stocks (SPY) outperforming bonds (TLT) = greed."""
    spy = history.get("SPY")
    tlt = history.get("TLT")
    if spy is None or tlt is None or "Close" not in spy or "Close" not in tlt:
        return None
    rs = ind.relative_strength(spy["Close"], tlt["Close"])
    if rs is None:
        return None
    return ind.to_0_100(rs, low=-0.10, high=0.10)


def _credit_score(history: Dict[str, pd.DataFrame]) -> Optional[float]:
    """0..100: junk bonds (HYG) outperforming IG (LQD) = greed (risk appetite)."""
    hyg = history.get("HYG")
    lqd = history.get("LQD")
    if hyg is None or lqd is None or "Close" not in hyg or "Close" not in lqd:
        return None
    rs = ind.relative_strength(hyg["Close"], lqd["Close"])
    if rs is None:
        return None
    return ind.to_0_100(rs, low=-0.05, high=0.05)


def _breadth_score(history: Dict[str, pd.DataFrame], tickers: List[str]) -> Optional[float]:
    """0..100: fraction of sector ETFs trading above their trend MA."""
    above_count = 0
    total = 0
    for ticker in tickers:
        df = history.get(ticker)
        if df is None or "Close" not in df:
            continue
        frac = ind.above_ma_fraction(df["Close"], config.TREND_MA_PERIOD)
        if frac is None:
            continue
        total += 1
        if frac > 0:
            above_count += 1
    if total == 0:
        return None
    return (above_count / total) * 100.0


def _average(scores: List[Optional[float]]) -> Optional[float]:
    """Average the non-None sub-scores, or None if all are missing."""
    present = [s for s in scores if s is not None]
    if not present:
        return None
    return sum(present) / len(present)


def compute_area_score(
    area: str,
    history: Dict[str, pd.DataFrame],
) -> Optional[Dict[str, object]]:
    """
    Compute the Fear & Greed score for one area.

    Args:
        area: One of stocks / commodities / bonds / crypto.
        history: ticker -> price DataFrame covering that area's inputs.

    Returns:
        Dict with score (0..100), label, and area — or None if uncomputable.
    """
    cfg = config.FEAR_GREED_AREAS.get(area)
    if cfg is None:
        return None

    sub_scores: List[Optional[float]] = []

    if area == "stocks":
        sub_scores.append(_momentum_score(history.get("SPY")))
        sub_scores.append(_vix_score(history))
        sub_scores.append(_safe_haven_score(history))
        sub_scores.append(_credit_score(history))
        breadth_tickers = cfg.get("sector_breadth", [])  # type: ignore[assignment]
        sub_scores.append(_breadth_score(history, breadth_tickers))
    else:
        # Commodities / bonds / crypto: momentum + (inverse) volatility of the
        # primary instruments in the area.
        for ticker in cfg["tickers"]:  # type: ignore[index]
            sub_scores.append(_momentum_score(history.get(ticker)))
            sub_scores.append(_volatility_score(history.get(ticker)))

    score = _average(sub_scores)
    if score is None:
        logger.warning(f"No Fear&Greed inputs available for area '{area}'")
        return None

    score = round(score, 1)
    return {
        "area": area,
        "label_area": cfg["label"],
        "score": score,
        "label": score_label(score),
    }


def compute_all(history: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, object]]:
    """
    Compute Fear & Greed for all configured areas.

    Args:
        history: ticker -> price DataFrame covering all areas' inputs.

    Returns:
        Mapping area -> result dict (only areas that computed successfully).
    """
    out: Dict[str, Dict[str, object]] = {}
    for area in config.FEAR_GREED_AREAS:
        result = compute_area_score(area, history)
        if result is not None:
            out[area] = result
    return out
