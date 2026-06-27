# 📡 Regime Radar

**Know whether to be a buyer or a seller — at a glance.**

Regime Radar is a free, self-hosted dashboard that reads the overall "weather" of the
market and tells you which of four regimes you're in right now. That tells you whether
to lean **long**, lean **short**, or stay defensive — and which assets tend to win in
the current environment.

It's built for **traders and curious investors** who want a fast, honest read on market
conditions without paying for a data terminal. Everything runs on your own machine using
**free, keyless** data ([yfinance](https://github.com/ranaroussi/yfinance)) — no
account, no API key, no subscription.

> ⚠️ **Not financial advice.** This is an educational tool. Markets are risky; do your
> own research. The software is provided "as is" with no warranty (see [LICENSE](LICENSE)).

<!--
  📸 SCREENSHOT: add a screenshot of the running dashboard here — it's the single
  biggest thing that gets people to try a project. Take one of http://localhost:8000,
  save it as docs/screenshot.png, then uncomment the line below.
-->
<!-- ![Regime Radar dashboard](docs/screenshot.png) -->

---

## 🧭 The idea in 30 seconds

Markets move through four regimes, defined by two questions: **is growth rising or
falling?** and **is inflation rising or falling?** Each regime favors a different asset
class:

| | Inflation **falls** | Inflation **rises** |
|---|---|---|
| **Growth above trend** | 🟢 **RECOVERY** → favors **Stocks** | 🟡 **OVERHEAT** → favors **Commodities** |
| **Growth below trend** | 🔵 **REFLATION** → favors **Bonds** | 🔴 **STAGFLATION** → favors **Cash** |

**The clever part:** Regime Radar figures out which regime you're in *without paid macro
data*. It reads it straight from how different parts of the market are performing
relative to each other — because the market prices the regime in real time:

- **Energy & commodities outperforming?** → inflation is probably rising.
- **Tech & consumer-discretionary leading?** → growth is probably strong.
- **Defensives (utilities, staples) and long bonds leading?** → growth is probably weak.

---

## ✨ What you get

- **Live 2×2 regime board** — highlights the current quadrant and plots a dot showing
  exactly where the market sits, with a confidence score.
- **Per-quadrant benchmark assets** — the tradeable proxies (S&P 500, Nasdaq, Gold, Oil,
  Bitcoin, sector ETFs, Treasuries…) and how each is performing, so you can verify the
  call yourself.
- **4 Fear & Greed indexes** — one each for Stocks, Commodities, Bonds, and Crypto,
  computed transparently from free inputs (no black box).
- **Multiple timeframes** — from intraday to 1 year. The regime can differ by
  timeframe, and *that divergence is itself a signal*.
- **Year-long regime history chart** — see exactly when and how the regime shifted over
  the past year, with growth and inflation plotted over colored regime bands.
- **Live updates** — during market hours a WebSocket streams fast price updates, so you
  can keep it open on a second screen and watch it move.

---

## 🚀 Quick start

**Prerequisites:** Python **3.12+** installed.

```bash
# 1. clone the repo
git clone https://github.com/LucasVincentMaria/regime-radar.git
cd regime-radar

# 2. install dependencies
py -m pip install -r requirements.txt        # Windows
# python3 -m pip install -r requirements.txt # macOS / Linux

# 3. run the dashboard (starts the API + background data updater)
py scripts/run.py                            # Windows
# python3 scripts/run.py                     # macOS / Linux
```

Then open **http://localhost:8000** in your browser.

> The first launch fetches a year of data for ~40 assets, so give it **20–40 seconds**
> to populate. After that it stays fresh automatically. You need **no API key** to run
> it — the `.env` file is entirely optional.

---

## 📖 How to read the dashboard (the manual)

When you open the dashboard you'll see five things. Here's how to use each:

### 1. The regime headline (top)
A big colored label like **`RECOVERY`** with **Bias**, **Favored** asset, and
**Confidence**. This is the bottom line:
- **Bias: long** → the environment favors being a buyer.
- **Bias: short** → the environment favors caution / being a seller.
- **Confidence** → how clearly the market is in this regime (high = both axes strongly
  signed; low = the market is near a turning point and ambiguous).

### 2. The 2×2 board
The four quadrants from the table above. The **active quadrant is highlighted** and a
**white dot** marks the market's exact position:
- **Left ↔ right** = inflation (falling on the left, rising on the right).
- **Up ↕ down** = growth (above trend at the top, below trend at the bottom).
- A dot near the center means the regime is weak/uncertain; a dot in a corner means a
  strong, clear regime.

### 3. The timeframe selector (top right)
Switch between **Today, 5 Days, 1 Month, 3 Months, 6 Months, 1 Year**. The whole
dashboard recomputes for that window. **Comparing timeframes is the real skill:**
- *Short-term and long-term agree* → strong trend, trade with the bias.
- *They disagree* (e.g. 1-Year says OVERHEAT but 1-Month says REFLATION) → the regime is
  shifting. That's where the opportunities — and the risk — are.

### 4. Benchmark assets by regime
For each quadrant, a table of its proxy assets and their return over the timeframe.
**This is how you verify the call.** If the board says OVERHEAT, you should see Energy
and commodities at the top of their table. If they're not, treat the signal with
caution.

### 5. Regime history chart
Growth (blue) and inflation (orange) plotted weekly over the past year, on top of
**colored bands** showing which regime each week was in. Use it to see momentum: *Is the
market drifting deeper into a regime, or climbing out of one?* The chart's right edge
always matches the board on the same timeframe.

### 6. Fear & Greed gauges
A 0–100 sentiment score for each of Stocks, Commodities, Bonds, and Crypto.
**Extreme readings often precede reversals** — extreme greed can mean a pullback is due;
extreme fear can mean a bounce. Use it as a contrarian sanity check on the regime.

---

## 💡 A worked example

Suppose the dashboard shows:

> **OVERHEAT** · Bias: long · Favored: Commodities · Confidence: 80% · *(Energy +12%,
> Oil +18% at the top of the table; Stocks F&G: 72 Greed)*

How to read it:
- Growth is up **and** inflation is up → the classic OVERHEAT regime.
- Commodities/energy are the relative winners, confirmed by the asset table.
- A long bias is favored, but Stocks F&G at 72 (Greed) is a warning that equities may be
  stretched — so you might prefer energy/commodity exposure over chasing tech.
- If the **1-Month** timeframe flips to STAGFLATION while **1-Year** stays OVERHEAT,
  that's an early sign growth is rolling over — tighten risk.

*(Illustrative only — not a recommendation.)*

---

## 🧠 How the regime is computed

- **Growth axis** = cyclical sectors (`XLY`, `XLI`, `XLK`) vs. defensives
  (`XLP`, `XLU`, `XLV`), confirmed by copper (`HG=F`) and credit appetite (`HYG`/`LQD`).
- **Inflation axis** = inflation beneficiaries (`XLE`, `DBC`, `GC=F`) vs. long bonds
  (`TLT`), confirmed by the oil trend (`CL=F`).

Each axis is a score in `[-1, 1]`; their signs pick the quadrant and their magnitude
drives the confidence score. The market is plotted at `(inflation, growth)`. All
thresholds live in [`config.py`](config.py) and are easy to tune.

**Scoring detail:** each basket's score is the equal-weight average *return over the
window* (first vs. last price). A longer window measures a longer trend, so the same day
can read differently on a 1-month vs. a 3-month window — that's expected and useful.

**Regime history chart:** the weekly chart replays this exact calculation at each past
week, using a **trailing window that matches the selected timeframe**, so the chart's
right edge always agrees with the live board.

---

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
| `GET /api/history/series?timeframe=3mo` | **Year-long weekly regime backtest** (growth + inflation + quadrant per week) |
| `WS  /ws/live` | Live quote stream (pushes during market hours) |

Interactive API docs are auto-generated at **http://localhost:8000/docs** while the
server is running.

---

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

Keep the API private to your own frontend if you don't want others hitting it (a reverse
proxy with an allowlist, or a small auth token, is enough).

---

## 🛠️ Troubleshooting

- **`Errno 10048` / "address already in use"** — port 8000 is taken by an old run.
  Find and stop it: `netstat -ano | findstr :8000` (Windows), then
  `taskkill /F /PID <pid>`. Or change `PORT` in your `.env`.
- **`py` not found** — on macOS/Linux use `python3` instead of `py`.
- **Dashboard shows "waiting for first refresh…"** — the initial data fetch is still
  running. Give it 20–40 seconds on first launch.
- **Live quotes say "loading…" and never update** — that's normal when the **US market
  is closed**. Live streaming only runs during market hours; the regime board still
  updates on its schedule.
- **A few assets show no data** — yfinance occasionally rate-limits or a ticker is
  briefly unavailable. The dashboard skips missing assets and keeps working.

---

## 🔒 Security — secrets never hit GitHub

This repo is built so API keys can never be committed:

1. **`.gitignore`** excludes `.env`, `data/`, `*.db`, `*.parquet`, `*.key`, etc.
2. **Secrets only come from the environment** (`.env`, loaded via `python-dotenv`) —
   never hardcoded, never logged. `config.py` contains **no secrets**.
3. **Pre-commit guard hooks** (in [`.claude/`](.claude/)) actively **block** any attempt
   to write a secret into a tracked file or to `git add`/`commit` protected files.

If you contribute: put any key in `.env` (copy from `.env.example`), never inline.

---

## 🗂️ Project structure

```
regime-radar/
├── config.py          # all tickers, thresholds, timeframes (NO secrets)
├── app/               # FastAPI backend, data layer, regime engine, scheduler
├── frontend/          # single-page dashboard (HTML/CSS/JS, no build step)
├── scripts/run.py     # launcher (API + scheduler)
├── tests/             # unit tests for the regime / F&G math
└── .claude/           # committed pre-commit guard hooks
```

---

## 🧪 Tests

Deterministic unit tests on synthetic fixtures (no network):

```bash
py -m pytest tests/ -q
```

---

## 🛣️ Roadmap

- [x] Background scheduler + regime refresh
- [x] 2×2 board + asset tables + Fear & Greed gauges
- [x] Live WebSocket layer (market-hours streaming)
- [x] Year-long weekly regime history chart
- [x] Website embed guide
- [ ] Optional keyed sources: FRED (real CPI/GDP), Alpaca/Polygon (true ticks)
- [ ] Configurable alerts on regime change
- [ ] Light theme

Contributions and ideas are welcome — open an issue or a pull request.

---

## 📜 License

[MIT](LICENSE) — free to use, modify, and embed, including commercially.
Keep the copyright notice. No warranty.
