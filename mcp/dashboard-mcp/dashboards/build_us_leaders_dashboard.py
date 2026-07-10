#!/usr/bin/env python3
"""Build the 强势股趋势监控 Phase 1 MVP dashboard as a self-contained HTML.

Queries the repo-root daas.db for the 12 US-leader scraw_<sym>_daily tables + the 72
observation series, aligns them per-symbol by date, and writes a standalone
HTML file (Chart.js from CDN, data inlined as JSON) to:
    mcp/dashboard-mcp/dashboards/us-leaders-trend-monitor.html

Re-run after the daily cron (04:45 Asia/Shanghai indicator recompute) to
refresh the snapshot. Stdlib only (sqlite3 + json) — no deps.

    python3 mcp/dashboard-mcp/dashboards/build_us_leaders_dashboard.py
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

THIS = Path(__file__).resolve()
REPO = THIS.parent.parent.parent.parent  # mcp/dashboard-mcp/dashboards/ → repo root
DB = REPO / "mcp" / "daas.db"
OUT = THIS.parent / "us-leaders-trend-monitor.html"

INDEXES = ["SPY", "QQQ"]
LEADERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX"]
SYMBOLS = INDEXES + LEADERS
METRICS = ["ma5", "ma10", "ma20", "rsi14", "volstd20", "high20"]


def fnum(x):
    """Parse observation value (stored as str) → float or None."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    import math
    return v if not math.isnan(v) else None


def load_symbol(conn, sym):
    """Return {dates, close, high, ma5..high20} for one symbol, date-aligned."""
    cur = conn.cursor()
    rows = cur.execute(
        f'SELECT date, Close, High FROM scraw_{sym.lower()}_daily ORDER BY date ASC'
    ).fetchall()
    dates = [r[0] for r in rows]
    close = [fnum(r[1]) for r in rows]
    high = [fnum(r[2]) for r in rows]

    out = {"dates": dates, "close": close, "high": high}
    for m in METRICS:
        mrows = cur.execute(
            "SELECT date, value FROM observations WHERE source='yfinance' "
            "AND function_name=? AND indicator=? ORDER BY date ASC",
            (sym, f"{sym}_{m}"),
        ).fetchall()
        mdict = {r[0]: fnum(r[1]) for r in mrows}
        out[m] = [mdict.get(d) for d in dates]
    return out


def latest_summary(sym, s):
    """Latest non-null value per metric for the leader-board table."""
    def last(arr):
        for v in reversed(arr):
            if v is not None:
                return v
        return None

    close = last(s["close"])
    high20 = last(s["high20"])
    dist = None
    if close is not None and high20 not in (None, 0):
        dist = (close - high20) / high20 * 100.0
    return {
        "symbol": sym,
        "close": close,
        "ma5": last(s["ma5"]),
        "ma10": last(s["ma10"]),
        "ma20": last(s["ma20"]),
        "rsi14": last(s["rsi14"]),
        "volstd20": last(s["volstd20"]),
        "high20": high20,
        "dist_from_high": dist,
    }


def main():
    conn = sqlite3.connect(str(DB))
    try:
        series = {sym: load_symbol(conn, sym) for sym in SYMBOLS}
    finally:
        conn.close()

    latest = [latest_summary(sym, series[sym]) for sym in SYMBOLS]
    # Leader board default sort: volstd20 ascending (None → end)
    latest_sorted = sorted(
        latest,
        key=lambda r: (r["volstd20"] is None, r["volstd20"] if r["volstd20"] is not None else 0),
    )

    payload = {
        "indexes": INDEXES,
        "leaders": LEADERS,
        "symbols": SYMBOLS,
        "lastDate": max((s["dates"][-1] for s in series.values() if s["dates"]), default=""),
        "series": series,          # full aligned arrays for charts
        "latest": latest_sorted,   # leader-board rows
    }

    html = HTML_TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT}  ({OUT.stat().st_size:,} bytes)")
    print(f"  symbols: {len(SYMBOLS)}  last date: {payload['lastDate']}")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>强势股趋势监控 — Phase 1 MVP</title>
<script src="vendor/chart.umd.min.js"></script>
<script>
// Guard: if the vendored Chart.js failed to load, show a notice instead of
// silently leaving the canvases empty.
if (typeof Chart === 'undefined') {
  document.querySelectorAll('.chart-box').forEach(b => {
    b.innerHTML = '<div class="cdn-fail">⚠ Chart.js 未加载 — 请确认 vendor/chart.umd.min.js 存在</div>';
  });
}
</script>
<style>
  :root { --bg:#0f1419; --panel:#1a2028; --ink:#e4e7eb; --dim:#8b95a5; --accent:#3b82f6; --green:#22c55e; --red:#ef4444; --amber:#f59e0b; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; }
  header { padding:1rem 1.5rem; border-bottom:1px solid #2a3340; }
  header h1 { margin:0; font-size:1.25rem; font-weight:600; }
  header .sub { color:var(--dim); font-size:0.8rem; margin-top:0.25rem; }
  .wrap { max-width:1400px; margin:0 auto; padding:1rem 1.5rem 4rem; }
  .panel { background:var(--panel); border:1px solid #2a3340; border-radius:8px; padding:1rem 1.25rem; margin-bottom:1.25rem; }
  .panel h2 { margin:0 0 0.75rem; font-size:1rem; font-weight:600; color:var(--ink); }
  .hint { color:var(--dim); font-size:0.78rem; margin-bottom:0.75rem; }
  table { width:100%; border-collapse:collapse; }
  th, td { padding:0.45rem 0.6rem; text-align:right; white-space:nowrap; }
  th { color:var(--dim); font-weight:500; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.04em; border-bottom:1px solid #2a3340; }
  th.sym, td.sym { text-align:left; }
  tbody tr { cursor:pointer; border-bottom:1px solid #1f2630; }
  tbody tr:hover { background:#222b36; }
  tbody tr.sel { background:#1e3a5f; }
  td .tag { font-size:0.65rem; padding:1px 5px; border-radius:3px; margin-left:4px; vertical-align:middle; }
  .tag.breakout { background:rgba(34,197,94,0.18); color:var(--green); }
  .tag.oversold { background:rgba(239,68,68,0.18); color:var(--red); }
  .num-neg { color:var(--red); }
  .num-pos { color:var(--green); }
  .grids { display:grid; grid-template-columns:1fr 1fr; gap:1.25rem; }
  @media (max-width:1000px){ .grids{ grid-template-columns:1fr; } }
  .chart-box { position:relative; height:340px; }
  select { background:#0f1419; color:var(--ink); border:1px solid #2a3340; border-radius:4px; padding:0.3rem 0.5rem; font-size:0.85rem; }
  .ctrl { display:flex; align-items:center; gap:0.6rem; margin-bottom:0.5rem; }
  .ctrl label { color:var(--dim); font-size:0.8rem; }
  .legend { color:var(--dim); font-size:0.72rem; margin-top:0.4rem; }
  .cdn-fail { color:var(--amber); padding:1rem; }
</style>
</head>
<body>
<header>
  <h1>强势股趋势监控 — Phase 1 MVP <span style="color:var(--dim);font-weight:400;font-size:0.85rem;">(US Reference Set)</span></h1>
  <div class="sub">利弗莫尔 × 欧奈尔 监控面板 · 数据截至 <span id="lastDate">—</span> · 日K刷新 04:30 / 指标重算 04:45 (Asia/Shanghai)</div>
</header>
<div class="wrap">

  <!-- Leader board -->
  <div class="panel">
    <h2>龙头榜 — 按 volstd20 升序 (HV 压缩优先 = VCP 突破候选)</h2>
    <div class="hint">绿标 = 距 20 日高点 -2% 内 (突破位); 红标 = RSI14 &lt; 30 (超卖, 欧奈尔回踩买点). 点击行 → 详情图.</div>
    <table id="board">
      <thead><tr>
        <th class="sym">Symbol</th><th>Close</th><th>MA5</th><th>MA10</th><th>MA20</th>
        <th>RSI14</th><th>volstd20</th><th>high20</th><th>距高点%</th>
      </tr></thead>
      <tbody id="boardBody"></tbody>
    </table>
  </div>

  <!-- Market regime + Detail -->
  <div class="grids">
    <div class="panel">
      <h2>大盘温度计 — SPY (左轴 + MA + 突破位) & QQQ (右轴)</h2>
      <div class="chart-box"><canvas id="regimeChart"></canvas></div>
    </div>
    <div class="panel">
      <div class="ctrl">
        <label>龙头详情:</label>
        <select id="leaderSel"></select>
      </div>
      <h2>详情 — Close + MA20 + high20 (左轴) / volstd20 (右轴)</h2>
      <div class="chart-box"><canvas id="detailChart"></canvas></div>
    </div>
  </div>

  <!-- RSI panel -->
  <div class="panel">
    <h2>RSI14 全龙头 (30/70 带, 选中高亮)</h2>
    <div class="chart-box" style="height:280px;"><canvas id="rsiChart"></canvas></div>
  </div>

  <div class="panel">
    <div class="hint">Phase 1 MVP 范围: 日K + 基础指标 (MA/RSI/HV代理/20日新高). 暂不含 2h K线 / 复合突破信号 / 实时推送 / AI报告 / 次新股通道 (Phase 1b-4). 本页为构建时快照, 重跑 build_us_leaders_dashboard.py 刷新.</div>
  </div>
</div>

<script>
const D = __PAYLOAD__;
let leaderCharts = null; // Chart instances

function fmt(v, d=2){ return (v===null||v===undefined||isNaN(v)) ? "—" : Number(v).toFixed(d); }
function pct(v){ return (v===null||v===undefined||isNaN(v)) ? "—" : (v>=0?"+":"")+v.toFixed(2)+"%"; }

document.getElementById('lastDate').textContent = D.lastDate;

// ── Leader board ──
const tbody = document.getElementById('boardBody');
D.latest.forEach(r => {
  const distBreakout = r.dist_from_high !== null && r.dist_from_high >= -2 && r.dist_from_high <= 0;
  const oversold = r.rsi14 !== null && r.rsi14 < 30;
  const distCls = r.dist_from_high !== null && r.dist_from_high < 0 ? 'num-neg' : (r.dist_from_high>0?'num-pos':'');
  const tr = document.createElement('tr');
  tr.dataset.sym = r.symbol;
  tr.innerHTML = `<td class="sym">${r.symbol}${distBreakout?'<span class="tag breakout">突破位</span>':''}${oversold?'<span class="tag oversold">超卖</span>':''}</td>`
    + `<td>${fmt(r.close)}</td><td>${fmt(r.ma5)}</td><td>${fmt(r.ma10)}</td><td>${fmt(r.ma20)}</td>`
    + `<td>${fmt(r.rsi14,1)}</td><td>${fmt(r.volstd20,3)}</td><td>${fmt(r.high20)}</td>`
    + `<td class="${distCls}">${pct(r.dist_from_high)}</td>`;
  tr.addEventListener('click', () => selectLeader(r.symbol));
  tbody.appendChild(tr);
});

// ── Leader selector ──
const sel = document.getElementById('leaderSel');
D.leaders.forEach(s => { const o=document.createElement('option'); o.value=s; o.textContent=s; sel.appendChild(o); });
sel.addEventListener('change', () => selectLeader(sel.value));

function selectLeader(sym){
  sel.value = sym;
  document.querySelectorAll('#boardBody tr').forEach(tr => tr.classList.toggle('sel', tr.dataset.sym===sym));
  renderDetail(sym);
  if (rsiChart) { rsiChart.data.datasets.forEach(ds => ds.borderColor = ds._sym===sym ? ds._hi : ds._lo); rsiChart.update('none'); }
}

// ── Chart helpers (category scale, no date-adapter CDN needed) ──
function align(sym, key, refDates){
  const s = D.series[sym];
  if (s.dates.length === refDates.length && s.dates.every((d,i)=>d===refDates[i])) return s[key];
  const m = {}; s.dates.forEach((d,i)=>{ if(s[key][i]!==null) m[d]=s[key][i]; });
  return refDates.map(d => m.hasOwnProperty(d) ? m[d] : null);
}
function mkDs(label, data, color, yid){
  return { label, data, borderColor:color, backgroundColor:color, yAxisID:yid,
           pointRadius:0, borderWidth:1.4, tension:0.25, spanGaps:true };
}
const X_TICKS = { color:'#8b95a5', maxTicksLimit:8, autoSkip:true };
const X_GRID = { color:'#1f2630' };
const Y_LEFT = { position:'left', grid:{color:'#1f2630'}, ticks:{color:'#8b95a5'} };
function bandLine(val, color, label, refDates){
  return { label, data: refDates.map(()=>val), borderColor:color, backgroundColor:color,
           borderWidth:1, borderDash:[4,4], pointRadius:0, tension:0 };
}

// ── Market regime: SPY close + MA5/10/20 + high20 (left) | QQQ close (right) ──
const refDates = D.series.SPY.dates;
const regimeChart = new Chart(document.getElementById('regimeChart'), {
  type:'line',
  data:{ labels: refDates, datasets:[
    mkDs('SPY Close', align('SPY','close',refDates), '#e4e7eb','y'),
    mkDs('SPY MA5',   align('SPY','ma5',refDates),   '#f59e0b','y'),
    mkDs('SPY MA10',  align('SPY','ma10',refDates),  '#3b82f6','y'),
    mkDs('SPY MA20',  align('SPY','ma20',refDates),  '#a855f7','y'),
    mkDs('SPY 20d High', align('SPY','high20',refDates), '#22c55e','y'),
    mkDs('QQQ Close', align('QQQ','close',refDates), '#06b6d4','y1'),
  ]},
  options:{ responsive:true, maintainAspectRatio:false,
    interaction:{ mode:'index', intersect:false },
    scales:{ x:{ type:'category', grid:X_GRID, ticks:X_TICKS }, y:Y_LEFT,
             y1:{ position:'right', grid:{display:false}, ticks:{color:'#06b6d4'} } },
    plugins:{ legend:{ labels:{color:'#8b95a5', boxWidth:12, font:{size:11}} } } }
});

// ── Detail chart: selected leader Close + MA20 + high20 (left) / volstd20 (right) ──
let detailChart = null;
function renderDetail(sym){
  const s = D.series[sym];
  if (detailChart) detailChart.destroy();
  detailChart = new Chart(document.getElementById('detailChart'), {
    type:'line',
    data:{ labels: s.dates, datasets:[
      mkDs('Close', s.close, '#e4e7eb','y'),
      mkDs('MA20', s.ma20, '#a855f7','y'),
      mkDs('20d High', s.high20, '#22c55e','y'),
      mkDs('volstd20 (HV)', s.volstd20, '#f59e0b','y1'),
    ]},
    options:{ responsive:true, maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      scales:{ x:{ type:'category', grid:X_GRID, ticks:X_TICKS }, y:Y_LEFT,
               y1:{ position:'right', grid:{display:false}, ticks:{color:'#f59e0b'} } },
      plugins:{ legend:{ labels:{color:'#8b95a5', boxWidth:12, font:{size:11}} } } }
  });
}

// ── RSI panel: all 10 leaders + 30/70 bands ──
const rsiColors = ['#3b82f6','#22c55e','#f59e0b','#ef4444','#a855f7','#06b6d4','#ec4899','#84cc16','#14b8a6','#f97316'];
const rsiDs = [
  bandLine(70,'#ef4444','70',refDates),
  bandLine(30,'#22c55e','30',refDates),
  ...D.leaders.map((sym,i)=>{
    const c = rsiColors[i%rsiColors.length];
    return { label:sym, _sym:sym, _hi:c, _lo:'rgba(139,149,165,0.30)',
      data: align(sym,'rsi14',refDates),
      borderColor:c, backgroundColor:c, borderWidth:1.2, pointRadius:0, tension:0.25, spanGaps:true };
  }),
];
const rsiChart = new Chart(document.getElementById('rsiChart'), {
  type:'line',
  data:{ labels: refDates, datasets: rsiDs },
  options:{ responsive:true, maintainAspectRatio:false,
    interaction:{mode:'index',intersect:false},
    scales:{ x:{ type:'category', grid:X_GRID, ticks:X_TICKS },
             y:{ min:0, max:100, grid:X_GRID, ticks:{color:'#8b95a5'} } },
    plugins:{ legend:{ labels:{color:'#8b95a5', boxWidth:10, font:{size:10}} } } }
});

// Initial selection: first leader
selectLeader(D.leaders[0]);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
