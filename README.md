# 📡 Regime Radar

A free, self-hosted dashboard that visualizes the **current market regime** — so you
know when to have a **long bias**, when to have a **short bias**, and what is worth
daytrading right now.

It maps the market onto the classic **Growth × Inflation** 2×2:

| | Inflation **falls** | Inflation **rises** |
|---|---|---|
| **Growth above trend** | 🟢 **RECOVERY** → Stocks | 🟡 **OVERHEAT** → Commodities |
| **Growth below trend** | 🔵 **REFLATION** → Bonds | 🔴 **STAGFLATION** → Cash |

The clever part: the regime is **inferred from relative sector performance** — no paid
macro data needed. If Energy outperforms, inflation is likely rising. If Tech and
Consumer Discretionary lead, growth is strong. All data comes from **free, keyless
[yfinance](https://github.com/ranaroussi/yfinance)**.

> ⚠️ **Not financial advice.** This is an educational tool. Markets are risky; do your
> own research. The software is provided "as is" with no warranty (see [LICENSE](LICENSE)).

---

## ✨ Features

- **Live 2×2 regime board** — highlights the current quadrant with a confidence score.
- **Per-quadrant benchmark assets** — tradeable proxies (S&P 500, Nasdaq, Gold, Oil,
  Bitcoin, sector ETFs, Treasuries…) whose performance confirms the regime.
- **4 Fear & Greed indexes** — one each for Stocks, Commodities, Bonds, and Crypto,
  computed transparently from keyless inputs.
- **Multiple timeframes** — from intraday to 1 year, so you see both recent shifts and
  the bigger picture (the regime can differ by timeframe).
- **Year-long regime history chart** — a weekly backtest plots growth and inflation
  over the past year on top of colored regime bands, so you can see exactly when and
  how the regime shifted.
- **Hybrid updates** — a background job refreshes the macro picture every ~20 min; a
  live WebSocket layer streams fast updates during market hours for a second screen.
- **Runs 24/7 on localhost**, and is built to embed into your own website later.

---

## 🚀 Quick start

> **Windows note:** this project uses the `py` launcher. On macOS/Linux use `python3`.

```bash
# 1. install dependencies
py -m pip install -r requirements.txt

# 2. (optional) copy the env template — v1 needs NO keys
cp .env.example .env

# 3. run the dashboard (starts the API + background scheduler)
py scripts/run.py
```

Then open **http://localhost:8000** in your browser.

---

## 🧠 How the regime is computed

- **Growth axis** = cyclical sectors (`XLY`, `XLI`, `XLK`) vs. defensives
  (`XLP`, `XLU`, `XLV`), confirmed by copper (`HG=F`) and credit appetite (`HYG`/`LQD`).
- **Inflation axis** = inflation beneficiaries (`XLE`, `DBC`, `GC=F`) vs. long bonds
  (`TLT`), confirmed by the oil trend (`CL=F`).

Each axis is a score in `[-1, 1]`; their signs pick the quadrant and their magnitude
drives a confidence score. The market is plotted as a dot on the board at
`(inflation, growth)`. Because the calculation runs per timeframe, **the regime can
differ across timeframes** — e.g. long-term `OVERHEAT` but short-term `REFLATION`.
That divergence is the daytrading signal. All thresholds live in
[`config.py`](config.py) and are easy to tune.

**Scoring detail:** each basket's score is the equal-weight average *return over the
window* (first vs. last price). A longer window therefore measures a longer trend, so
the same day can read differently on a 1-month vs. a 3-month window — that's expected.

**Regime history chart:** the year-long weekly chart replays this exact calculation at
each past week, using a **trailing window that matches the selected timeframe**. So the
chart's right edge always agrees with the live board on the same timeframe. Switching
the timeframe dropdown re-scales both the board and the chart together.

## 🔌 API reference

The frontend is just one consumer — you can build your own against these endpoints:

| Endpoint | Description |
|---|---|
| `GET /api/health` | Status + last-update timestamps |
| `GET /api/meta` | Quadrants, timeframes, labels (static metadata) |
| `GET /api/snapshot?timeframe=3mo` | Full snapshot: regime + F&G + asset tables |
| `GET /api/regime?timeframe=3mo` | Just the regime result |
| `GET /api/feargreed?timeframe=3mo` | Just the 4 Fear & Greed scores |
| `GET /api/quotes` | Latest live quotes |
| `GET /api/history/regime?timeframe=3mo` | Regime time series (for charts) |
| `GET /api/history/feargreed?area=crypto` | Fear & Greed time series |
| `GET /api/history/series` | **Year-long weekly regime backtest** (growth + inflation + quadrant per week) |
| `WS  /ws/live` | Live quote stream (pushes during market hours) |

## 🌐 Embedding in your website

The dashboard is a single static page backed by an API, so you have two easy paths:

1. **iframe (simplest):** run this server (e.g. behind a reverse proxy at
   `radar.yoursite.com`) and embed it:
   ```html
   <iframe src="https://radar.yoursite.com/" width="100%" height="900"
           style="border:0"></iframe>
   ```
2. **Build your own UI:** call the JSON endpoints above from your existing site and
   render the data however you like. The regime math stays on this server.

Keep the API private to your own frontend if you don't want others hitting it (a
reverse proxy with an allowlist, or a small auth token, is enough).

---

## 🔒 Security — secrets never hit GitHub

This repo is built so API keys can never be committed:

1. **`.gitignore`** excludes `.env`, `data/`, `*.db`, `*.parquet`, `*.key`, etc.
2. **Secrets only come from the environment** (`.env`, loaded via `python-dotenv`) —
   never hardcoded, never logged. `config.py` contains **no secrets**.
3. **Claude Code hooks** (in [`.claude/`](.claude/)) actively **block** any attempt to
   write a secret into a tracked file or to `git add`/`commit` protected files. These
   are committed, so they protect every contributor and every AI session automatically.

If you contribute: put any key in `.env` (copy from `.env.example`), never inline.

---

## 🗂️ Project structure

```
regime-radar/
├── config.py          # all tickers, thresholds, timeframes (NO secrets)
├── app/               # FastAPI backend, data layer, regime engine, scheduler
├── frontend/          # minimal static dashboard (HTML/CSS/JS)
├── scripts/run.py     # launcher (API + scheduler)
├── tests/             # unit tests for the regime / F&G math
└── .claude/           # committed security hooks
```

---

## 🧪 Tests

Deterministic unit tests on synthetic fixtures (no network):

```bash
py -m pytest tests/ -q
```

## 🛣️ Roadmap

- [x] Background scheduler + slow regime refresh
- [x] 2×2 board + asset tables + F&G gauges (frontend v1)
- [x] Live WebSocket layer (market-hours streaming)
- [x] Website embed guide
- [x] Year-long weekly regime history chart
- [ ] Optional keyed sources: FRED (real CPI/GDP), Alpaca/Polygon (true ticks)
- [ ] Configurable alerts on regime change

---

## 📜 License

[MIT](LICENSE) — free to use, modify, and embed, including commercially.
Keep the copyright notice. No warranty.
