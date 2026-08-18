# DaaS 指标浏览器

**Slug**: `daas-indicator-explorer`
**HTML**: `file:///Users/chengsishi/code/daas/mcp/dashboard-mcp/dashboards/daas-indicator-explorer.html`
**Builder**: `mcp/dashboard-mcp/dashboards/build_indicator_explorer_dashboard.py` (re-run to refresh the baked data)

## 介绍

DaaS 全量指标浏览器。在一个页面里浏览 daas 计算出的每一个指标：从指标目录（136 条有数据 + 3 条已注册但源表缺失）中任选一个，查看其时间序列、来源（源表 / 值列 / op / 规则名）与快速统计（最新值、环比、最小/最大、行数、日期范围）。覆盖 yfinance 个股技术指标（12 只标的 × MA5/10/20、RSI14、20日波动率、20日新高）与 massive 宏观序列（国债收益率、通胀、通胀预期、劳动力市场，跨 level/SMA/EMA/zscore/pct_change/rolling_std）。用于回答「daas 里有哪些指标，长什么样」。

## 范围

- **实体范围（页内 `<select>`）**: 指标本身，按来源分组（17 个 `<optgroup>`）：
  - `yfinance` — 12 只标的（AAPL/AMD/AMZN/AVGO/GOOGL/META/MSFT/NFLX/NVDA/QQQ/SPY/TSLA）× 6 个指标（ma5/ma10/ma20、rsi14、volstd20、high20）
  - `massive` — Treasury Yields / Inflation / Inflation Expectations / Labor Market 四组，各跨 level / sma / ema / zscore / pct_change / rolling_std
  - `wbdata` — 3 条（gdp_level_usd / population_total / gdp_growth_annual_pct），灰显「无数据」（源表 `wbdata_*` 未回填）
- **时间范围**: 1947-01-01 ~ 2026-07-02（每条指标各自的全量区间；日期输入框随选中指标自动切换到该指标的 min/max，可再收窄）

## 数据来源

- **`observations`** — 图表主线。`source` + `indicator` 定位序列，`date` 为 x 轴，`value` 为 y 轴。共烘焙 140,439 条观测值（136 个有数据的指标）。
- **`indicator_rules`** — 目录表。每条规则的 `indicator_name` / `datasource` / `op` / `value_column` / `source_table` / `function_name` / 观测行数 / 日期范围 / 最新值，共 139 行（含 3 条 wbdata 无数据）。点击任一行即在图表中加载该指标。

## 刷新方式

静态快照——数据烘焙在 HTML 里，不联网。重新生成以刷新：

```bash
uv run --directory mcp/dashboard-mcp python dashboards/build_indicator_explorer_dashboard.py
```

底层观测值的来源：
- yfinance 指标由既有 akshare/yfinance cron 每日抓取 + `run_indicator` 计算（参见 `us-leaders-trend-monitor` 看板的 cron）。
- massive 指标由 `backfill_massive.py` 回填 `scraw_massive_*` 后经 `run_indicator` 计算。
- 若新增/重算指标后想让看板反映，先 `daas-mcp --run-indicator <rule_name>` 写入 `observations`，再重跑上面的 builder。

> 注：本看板构建时已一次性补跑 59 条此前未计算的 massive 指标（`level_*` / `sma12_*` / `zscore12_*` / `pct_change_*` / `ema20_*` / `rolling_std30_*`），使 massive 从 4 条有数据变为 64 条全量有数据。wbdata 3 条因源表 `wbdata_ny_gdp_mktp_cd` / `wbdata_sp_pop_totl` / `wbdata_ny_gdp_mktp_kd_zg` 不存在而无法计算，在目录中标记为「无数据」。
