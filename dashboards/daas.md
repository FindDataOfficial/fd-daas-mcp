# Dashboards

| Title | Intro | URL | Source | Refresh |
|---|---|---|---|---|
| 强势股趋势监控 — Phase 1 MVP | Livermore×O'Neil 强势股趋势监控看板。展示美股 leadership 候选标的的日行情（OHLCV）与趋势指标（MA5/10/20、RSI14、20日波动率、20日新高）每日快照，用于识别处于趋势确立 / 加速阶段的强势股。Phase 1 MVP。 | [us-leaders-trend-monitor.html](us-leaders-trend-monitor.html) | scraw_aapl_daily, scraw_amd_daily, scraw_amzn_daily, scraw_avgo_daily, scraw_googl_daily, scraw_meta_daily, scraw_msft_daily, scraw_nflx_daily, scraw_nvda_daily, scraw_qqq_daily, scraw_spy_daily, scraw_tsla_daily, observations | daily 04:30 fetch / 04:45 indicators (Asia/Shanghai); rebuild HTML via build_us_leaders_dashboard.py |
| AAPL 日行情快照 | Apple Inc. (AAPL) 日收盘价看板。展示 scraw_aapl_daily 表中的每日收盘价，支持按时间区间筛选，用于快速查看 AAPL 近一年走势。 | [aapl-daily-snapshot.html](aapl-daily-snapshot.html) | scraw_aapl_daily | static snapshot (rebuild via fd-daas-dashboard-creator) |
| DaaS 指标浏览器 | DaaS 全量指标浏览器。在一个页面里浏览 daas 计算出的每一个指标：从指标目录（136 条有数据 + 3 条已注册但源表缺失）中任选一个，查看其时间序列、来源（源表 / 值列 / op / 规则名）与快速统计（最新值、环比、最小/最大、行数、日期范围）。覆盖 yfinance 个股技术指标（12 只标的 × MA5/10/20、RSI14、20日波动率、20日新高）与 massive 宏观序列（国债收益率、通胀、通胀预期、劳动力市场，跨 level/SMA/EMA/zscore/pct_change/rolling_std）。用于回答「daas 里有哪些指标，长什么样」。静态快照，重新生成以刷新。 | [daas-indicator-explorer.html](daas-indicator-explorer.html) | observations, indicator_rules | 静态快照（重新生成以刷新；yfinance 指标由既有 cron 驱动，massive 指标由 Massive backfill 驱动） |
