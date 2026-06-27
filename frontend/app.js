/*
  Regime Radar — frontend logic.

  Plain JavaScript, no framework. It does three things:
    1. Loads static metadata (timeframes, quadrant colors) once.
    2. Polls the REST API for the current snapshot and renders the board,
       Fear & Greed gauges, and asset tables.
    3. Opens a WebSocket for live quotes (active during market hours).

  Read it top to bottom — each section is small and commented.
*/

"use strict";

// ── Small helpers ──────────────────────────────────────────
const $ = (id) => document.getElementById(id);

/** GET a JSON endpoint, returning null on any error (so the UI never crashes). */
async function getJSON(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch (_) {
    return null;
  }
}

/** Format a number with a sign and fixed decimals, e.g. +1.23. */
function signed(n, digits = 2) {
  if (n === null || n === undefined) return "—";
  return (n >= 0 ? "+" : "") + n.toFixed(digits);
}

// ── State ──────────────────────────────────────────────────
let META = null;                 // static metadata from /api/meta
let currentTimeframe = null;     // selected timeframe key

// ── 1. Bootstrap ───────────────────────────────────────────
async function init() {
  META = await getJSON("/api/meta");
  if (!META) {
    setStatus("API unavailable", "err");
    return;
  }

  // Populate the timeframe dropdown.
  const select = $("timeframe");
  select.innerHTML = "";
  for (const [key, label] of Object.entries(META.timeframes)) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = label;
    select.appendChild(opt);
  }
  currentTimeframe = META.default_timeframe;
  select.value = currentTimeframe;
  select.addEventListener("change", () => {
    currentTimeframe = select.value;
    refresh();
    loadHistoryChart();  // chart window follows the selected timeframe
  });

  await refresh();
  connectLive();
  loadHistoryChart();

  // Re-poll the slow snapshot every 60s (the backend recomputes every ~20m,
  // but polling cheaply catches the update without a page reload).
  setInterval(refresh, 60_000);
  // The weekly history changes slowly; refresh it every 30 min.
  setInterval(loadHistoryChart, 30 * 60_000);
}

function setStatus(text, cls) {
  const el = $("status");
  el.textContent = text;
  el.className = "status" + (cls ? " " + cls : "");
}

// ── 2. Render the current snapshot ─────────────────────────
async function refresh() {
  const snap = await getJSON(`/api/snapshot?timeframe=${currentTimeframe}`);
  if (!snap) {
    setStatus("waiting for first refresh…", "err");
    return;
  }
  setStatus("live", "ok");

  renderRegime(snap.regime);
  renderGauges(snap.feargreed);
  renderAssets(snap.assets);

  const health = await getJSON("/api/health");
  if (health && health.last_updated) {
    $("last-updated").textContent = new Date(health.last_updated).toLocaleString();
  }
}

/** Highlight the active quadrant, move the dot, fill the headline. */
function renderRegime(regime) {
  document.querySelectorAll(".cell").forEach((c) => c.classList.remove("active"));
  if (!regime) {
    $("headline-quadrant").textContent = "no data";
    return;
  }

  const cell = document.querySelector(`.cell[data-quadrant="${regime.quadrant}"]`);
  if (cell) cell.classList.add("active");

  // Headline.
  const hq = $("headline-quadrant");
  hq.textContent = regime.quadrant;
  hq.style.borderColor = regime.color || "#888";
  $("headline-bias").textContent = regime.bias;
  $("headline-favored").textContent = regime.favored;
  $("headline-confidence").textContent = Math.round(regime.confidence * 100) + "%";

  // Axis scores.
  $("score-growth").textContent = signed(regime.growth);
  $("score-inflation").textContent = signed(regime.inflation);

  // Plot the dot: inflation drives x (-1 left → +1 right),
  // growth drives y (+1 top → -1 bottom). Map [-1,1] → [10%,90%].
  const x = 50 + regime.inflation * 40;
  const y = 50 - regime.growth * 40;
  const dot = $("board-dot");
  dot.style.left = `${Math.max(8, Math.min(92, x))}%`;
  dot.style.top = `${Math.max(8, Math.min(92, y))}%`;
}

/** Draw the four Fear & Greed gauges. */
function renderGauges(feargreed) {
  const wrap = $("gauges");
  wrap.innerHTML = "";
  if (!feargreed) return;

  for (const [area, data] of Object.entries(feargreed)) {
    const g = document.createElement("div");
    g.className = "gauge";
    g.innerHTML = `
      <div class="gauge-title">${data.label_area}</div>
      <div class="gauge-bar">
        <div class="gauge-marker" style="left:${data.score}%"></div>
      </div>
      <div class="gauge-score">${data.score.toFixed(0)}</div>
      <div class="gauge-label">${data.label}</div>
    `;
    wrap.appendChild(g);
  }
}

/** Render one benchmark-asset table per quadrant. */
function renderAssets(assets) {
  const grid = $("asset-grid");
  grid.innerHTML = "";
  if (!assets) return;

  for (const [quadrant, rows] of Object.entries(assets)) {
    const card = document.createElement("div");
    card.className = "asset-card";
    const color = (META.quadrants[quadrant] || {}).color || "#888";

    const body = rows.map((r) => {
      const ret = r.return_pct;
      const cls = ret === null ? "" : ret >= 0 ? "pos" : "neg";
      const retTxt = ret === null ? "—" : signed(ret) + "%";
      return `<tr><td>${r.label}</td><td class="${cls}">${retTxt}</td></tr>`;
    }).join("");

    card.innerHTML = `
      <h3 style="color:${color}">${quadrant}</h3>
      <table><tbody>${body}</tbody></table>
    `;
    grid.appendChild(card);
  }
}

// ── 2b. Regime history chart (Chart.js) ────────────────────
let historyChart = null;  // holds the Chart.js instance so we can update it

/**
 * Chart.js plugin: paint a colored vertical band behind each datapoint based on
 * that week's regime quadrant. This makes regime shifts visible at a glance.
 */
const regimeBandsPlugin = {
  id: "regimeBands",
  beforeDatasetsDraw(chart, _args, opts) {
    const points = opts.points || [];
    if (!points.length) return;
    const { ctx, chartArea, scales } = chart;
    const x = scales.x;
    ctx.save();
    points.forEach((p, i) => {
      // Each band spans from the midpoint before to the midpoint after.
      const left = i === 0 ? chartArea.left : (x.getPixelForValue(i - 1) + x.getPixelForValue(i)) / 2;
      const right = i === points.length - 1 ? chartArea.right : (x.getPixelForValue(i) + x.getPixelForValue(i + 1)) / 2;
      ctx.fillStyle = hexToRgba(p.color || "#444", 0.16);
      ctx.fillRect(left, chartArea.top, right - left, chartArea.bottom - chartArea.top);
    });
    ctx.restore();
  },
};

/** Convert a #rrggbb color to an rgba() string with the given alpha. */
function hexToRgba(hex, alpha) {
  const m = hex.replace("#", "");
  const r = parseInt(m.substring(0, 2), 16);
  const g = parseInt(m.substring(2, 4), 16);
  const b = parseInt(m.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Fetch the weekly history for the current timeframe and (re)draw the chart. */
async function loadHistoryChart() {
  const data = await getJSON(`/api/history/series?timeframe=${currentTimeframe}`);
  if (!data || !data.points || !data.points.length) return;

  const points = data.points;
  const labels = points.map((p) => p.date);
  const growth = points.map((p) => p.growth);
  const inflation = points.map((p) => p.inflation);

  // Subtitle clarifies that each weekly point uses a trailing window matching
  // the selected timeframe (so the chart's right edge agrees with the board).
  const sub = $("chart-subtitle");
  if (sub) {
    const tfLabel = (META.timeframes && META.timeframes[data.timeframe]) || data.timeframe;
    sub.textContent = `— 1 year, weekly · ${data.window_days}-day window (matches ${tfLabel})`;
  }

  renderChartLegend();

  const cfg = {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Growth",
          data: growth,
          borderColor: "#4aa3ff",
          backgroundColor: "#4aa3ff",
          borderWidth: 2, tension: 0.25, pointRadius: 0, pointHoverRadius: 4,
        },
        {
          label: "Inflation",
          data: inflation,
          borderColor: "#ff8c42",
          backgroundColor: "#ff8c42",
          borderWidth: 2, tension: 0.25, pointRadius: 0, pointHoverRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { ticks: { color: "#8b949e", maxTicksLimit: 12 }, grid: { color: "rgba(255,255,255,0.04)" } },
        y: {
          min: -1, max: 1,
          ticks: { color: "#8b949e" }, grid: { color: "rgba(255,255,255,0.06)" },
          title: { display: true, text: "score (-1 … +1)", color: "#8b949e" },
        },
      },
      plugins: {
        legend: { display: false },               // we draw our own legend
        regimeBands: { points },                  // feed the band plugin
        tooltip: {
          callbacks: {
            // Show which quadrant each week was in.
            afterBody: (items) => {
              const i = items[0].dataIndex;
              return `Regime: ${points[i].quadrant}`;
            },
          },
        },
      },
    },
    plugins: [regimeBandsPlugin],
  };

  if (historyChart) {
    // Update in place so the chart doesn't flicker on refresh.
    historyChart.data = cfg.data;
    historyChart.options.plugins.regimeBands.points = points;
    historyChart.update();
  } else {
    const ctx = $("history-chart").getContext("2d");
    historyChart = new Chart(ctx, cfg);
  }
}

/** Build the legend (growth/inflation lines + the 4 regime band colors). */
function renderChartLegend() {
  const el = $("chart-legend");
  if (!el || !META) return;
  const lines = [
    `<span class="legend-item"><span class="legend-line" style="background:#4aa3ff"></span>Growth</span>`,
    `<span class="legend-item"><span class="legend-line" style="background:#ff8c42"></span>Inflation</span>`,
  ];
  const bands = Object.entries(META.quadrants).map(([name, q]) =>
    `<span class="legend-item"><span class="legend-swatch" style="background:${q.color}"></span>${name}</span>`
  );
  el.innerHTML = lines.concat(bands).join("");
}

// ── 3. Live WebSocket layer ────────────────────────────────
function connectLive() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`);

  ws.onmessage = (event) => {
    let msg;
    try { msg = JSON.parse(event.data); } catch (_) { return; }
    if (msg.type === "quotes") renderQuotes(msg.quotes);
  };

  ws.onopen = () => $("live-dot").className = "live-dot on";
  ws.onclose = () => {
    $("live-dot").className = "live-dot off";
    // Auto-reconnect after a short delay so a dropped socket self-heals.
    setTimeout(connectLive, 3000);
  };
  ws.onerror = () => ws.close();
}

/** Fill the live-quotes table from a {ticker: price} map. */
function renderQuotes(quotes) {
  const body = $("quotes-body");
  const labels = (META && META.asset_labels) || {};
  const rows = Object.entries(quotes).map(([t, price]) => {
    const label = labels[t] || t;
    return `<tr><td>${label}</td><td>${Number(price).toLocaleString(undefined, {maximumFractionDigits: 2})}</td></tr>`;
  });
  body.innerHTML = rows.length ? rows.join("") : "<tr><td>no quotes yet</td></tr>";
}

// Kick everything off once the DOM is ready.
window.addEventListener("DOMContentLoaded", init);
