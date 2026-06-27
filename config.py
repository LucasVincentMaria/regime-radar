"""
Central configuration for Regime Radar.

Everything tunable lives here: tickers, regime thresholds, timeframes, and
intervals. NO secrets in this file — those are read from the environment
(see .env.example). This module is safe to commit to GitHub.

The design philosophy (per project guidelines): no magic numbers scattered in
code. If you want to tune the regime model, change values *here*.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────
ROOT_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = ROOT_DIR / "data"
CACHE_DIR: Path = DATA_DIR / "cache"
DB_PATH: Path = DATA_DIR / "regime.db"
FRONTEND_DIR: Path = ROOT_DIR / "frontend"

# ─────────────────────────────────────────────────────────────
# Server (overridable via .env, never required)
# ─────────────────────────────────────────────────────────────
HOST: str = os.environ.get("HOST", "127.0.0.1")
PORT: int = int(os.environ.get("PORT", "8000"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

# ─────────────────────────────────────────────────────────────
# Regime quadrants (the Growth × Inflation 2×2)
# ─────────────────────────────────────────────────────────────
# Each quadrant maps a (growth_direction, inflation_direction) to a name,
# the favored asset class, and a trading bias hint.
QUADRANTS: Dict[str, Dict[str, str]] = {
    "RECOVERY": {
        "growth": "up",
        "inflation": "down",
        "favored": "STOCKS",
        "bias": "long",
        "color": "#2e9e4f",  # green
    },
    "OVERHEAT": {
        "growth": "up",
        "inflation": "up",
        "favored": "COMMODITIES",
        "bias": "long",
        "color": "#f2c014",  # yellow
    },
    "REFLATION": {
        "growth": "down",
        "inflation": "down",
        "favored": "BONDS",
        "bias": "neutral",
        "color": "#1f6fb2",  # blue
    },
    "STAGFLATION": {
        "growth": "down",
        "inflation": "up",
        "favored": "CASH",
        "bias": "short",
        "color": "#c0392b",  # red
    },
}

# ─────────────────────────────────────────────────────────────
# Benchmark asset baskets per quadrant (keyless yfinance tickers)
# These are the tradeable proxies whose relative performance confirms
# the regime. See README for the rationale behind each.
# ─────────────────────────────────────────────────────────────
QUADRANT_ASSETS: Dict[str, List[str]] = {
    "RECOVERY": [
        "SPY", "QQQ", "XLK", "XLI", "XLB", "XLF", "XLC", "XLY",
    ],
    "OVERHEAT": [
        "GC=F", "CL=F", "BZ=F", "NG=F", "XLE", "XOP", "DBC", "DBA",
        "HG=F", "SI=F", "BTC-USD", "ETH-USD",
    ],
    "REFLATION": [
        "TLT", "IEF", "BND", "XLU", "XLP", "XLV", "GLD",
    ],
    "STAGFLATION": [
        "BIL", "SHV", "UUP", "GC=F", "GLD", "XLE", "DBC", "XLP", "XLU", "XLV",
    ],
}

# ─────────────────────────────────────────────────────────────
# Macro-axis baskets — how Growth and Inflation are inferred from
# relative sector performance (keyless). This is the core trick:
# we never need a macro API key for v1.
# ─────────────────────────────────────────────────────────────
# Growth axis: cyclicals (risk-on) vs defensives (risk-off).
GROWTH_CYCLICALS: List[str] = ["XLY", "XLI", "XLK"]
GROWTH_DEFENSIVES: List[str] = ["XLP", "XLU", "XLV"]
# Confirmation: copper (Dr. Copper) and credit risk appetite (junk vs IG).
GROWTH_CONFIRM: List[str] = ["HG=F", "HYG", "LQD"]

# Inflation axis: inflation beneficiaries vs long-duration bonds.
INFLATION_BENEFICIARIES: List[str] = ["XLE", "DBC", "GC=F"]
INFLATION_DEFLATORS: List[str] = ["TLT"]
# Confirmation: oil trend.
INFLATION_CONFIRM: List[str] = ["CL=F"]

# ─────────────────────────────────────────────────────────────
# Headline assets the user watches live (fast WebSocket layer)
# ─────────────────────────────────────────────────────────────
LIVE_ASSETS: List[str] = [
    "SPY", "QQQ", "BTC-USD", "ETH-USD", "GC=F", "CL=F", "TLT", "^VIX",
]

# Friendly display names for the UI (ticker -> label).
ASSET_LABELS: Dict[str, str] = {
    "SPY": "S&P 500", "QQQ": "Nasdaq 100", "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum", "GC=F": "Gold", "CL=F": "WTI Crude",
    "BZ=F": "Brent Crude", "NG=F": "Nat Gas", "HG=F": "Copper",
    "SI=F": "Silver", "TLT": "20y+ Treasuries", "IEF": "7-10y Treasuries",
    "BND": "Total Bond", "GLD": "Gold ETF", "BIL": "1-3m T-Bills",
    "UUP": "US Dollar", "^VIX": "VIX",
    "XLK": "Technology", "XLI": "Industrials", "XLB": "Materials",
    "XLF": "Financials", "XLC": "Communication", "XLY": "Cons. Discr.",
    "XLE": "Energy", "XLP": "Cons. Staples", "XLU": "Utilities",
    "XLV": "Health Care", "XOP": "Oil & Gas E&P", "DBC": "Commodities",
    "DBA": "Agriculture", "HYG": "High-Yield Bonds", "LQD": "IG Bonds",
    "SHV": "Short Treasuries",
}

# ─────────────────────────────────────────────────────────────
# Fear & Greed — one composite (0-100) per asset area
# Inputs are keyless; weights sum to 1.0 per area.
# ─────────────────────────────────────────────────────────────
FEAR_GREED_AREAS: Dict[str, Dict[str, object]] = {
    "stocks": {
        "label": "Stocks",
        "tickers": ["SPY", "TLT", "HYG", "LQD", "^VIX"],
        "sector_breadth": ["XLK", "XLI", "XLB", "XLF", "XLC", "XLY",
                           "XLE", "XLP", "XLU", "XLV"],
    },
    "commodities": {
        "label": "Commodities",
        "tickers": ["DBC", "CL=F", "GC=F", "HG=F"],
    },
    "bonds": {
        "label": "Bonds",
        "tickers": ["TLT", "IEF", "HYG", "LQD"],
    },
    "crypto": {
        "label": "Crypto",
        "tickers": ["BTC-USD", "ETH-USD"],
    },
}

# ─────────────────────────────────────────────────────────────
# Timeframes — lookbacks the regime & F&G scores are computed over.
# yfinance period/interval pairs. Order = short → long for the UI.
# ─────────────────────────────────────────────────────────────
TIMEFRAMES: Dict[str, Dict[str, str]] = {
    "1d":  {"period": "1d",  "interval": "5m",  "label": "Today"},
    "5d":  {"period": "5d",  "interval": "30m", "label": "5 Days"},
    "1mo": {"period": "1mo", "interval": "1d",  "label": "1 Month"},
    "3mo": {"period": "3mo", "interval": "1d",  "label": "3 Months"},
    "6mo": {"period": "6mo", "interval": "1d",  "label": "6 Months"},
    "1y":  {"period": "1y",  "interval": "1d",  "label": "1 Year"},
}
DEFAULT_TIMEFRAME: str = "3mo"

# Moving-average lookback used for "above/below trend" judgments (in bars).
TREND_MA_PERIOD: int = 50

# How strong a relative-strength reading must be (in normalized score units,
# roughly std-devs) before we call an axis confidently "up" or "down".
# Below this, the axis is "neutral" / low confidence.
AXIS_CONFIDENCE_THRESHOLD: float = 0.15

# ─────────────────────────────────────────────────────────────
# Update intervals & rate limiting
# ─────────────────────────────────────────────────────────────
SLOW_REFRESH_MINUTES: int = 20          # background regime refresh cadence
LIVE_POLL_SECONDS: int = 8              # fast layer poll cadence (market hours)
MAX_CONCURRENT_FETCHES: int = 8        # asyncio.Semaphore limit
CACHE_TTL_SECONDS: int = 300           # Parquet cache freshness window

# ─────────────────────────────────────────────────────────────
# Market hours (NYSE) — used to gate the live layer.
# ─────────────────────────────────────────────────────────────
MARKET_CALENDAR: str = "NYSE"
MARKET_TIMEZONE: str = "America/New_York"

# ─────────────────────────────────────────────────────────────
# Weekly regime history (year-long backtest chart)
# ─────────────────────────────────────────────────────────────
# We fetch this many days of daily prices, then replay the regime engine at
# weekly steps using a trailing window, to build a real 1-year history.
HISTORY_LOOKBACK_DAYS: int = 365            # how far back the chart spans
HISTORY_STEP_DAYS: int = 7                  # weekly datapoints
HISTORY_CACHE_TTL_SECONDS: int = 3600       # recompute at most hourly

# The chart's trailing window per weekly point MATCHES the selected timeframe,
# so the chart's right edge always agrees with the live board. The window is in
# CALENDAR days chosen to span the same period yfinance returns for each
# timeframe (e.g. period="3mo" ≈ 3 calendar months ≈ 91 days). Very short
# timeframes use a 1-month floor so a weekly-stepped year still makes sense.
HISTORY_WINDOW_DAYS_BY_TIMEFRAME: Dict[str, int] = {
    "1d":  30,    # floor: 1-day windows can't be weekly-stepped meaningfully
    "5d":  30,
    "1mo": 30,
    "3mo": 91,
    "6mo": 182,
    "1y":  365,
}
HISTORY_DEFAULT_WINDOW_DAYS: int = 91       # fallback (~3 months)
