# 强势股趋势交易策略 - 工程路线图

> 利弗莫尔 × 欧奈尔 × AI 监控版 + 次新股绿色通道
> 目标市场: 美股 (SPY/QQQ 基准, yfinance)
> 本文记录 Phase 2 已交付范围 + 后续 80% 自定义工程的实施计划。

## 现状 (Phase 2, 2026-07-16)

已通过 `fd-daas-research` skill 链交付:

| 组件 | 状态 | 位置 |
|---|---|---|
| 30 龙头池 + SPY/QQQ 实体 + yfinance 链接 | ✅ | `entities` / `entity_datasource_links` |
| `us_leadership_pool` collection (30 只) | ✅ | `entity_collections` |
| 32 只日K OHLCV (yfinance 1y, 截至 2026-07-15) | ✅ | `scraw_<sym>_daily` |
| 192 条指标规则 (MA5/10/20, RSI14, volstd20, high20 × 32) | ✅ | `indicator_rules` / `observations` |
| 12 条飞书预警代理 (10×RSI突破70 + SPY/QQQ日跌>1%) | ✅ | `alert_rules` (alerts-mcp) |
| Phase 2 看板 (龙头榜+RS排名+池A+详情+RSI) | ✅ | `fd-daas-mcp/dashboard-mcp/dashboards/build_us_leaders_dashboard.py` |

### Phase 2 已知局限 (诚实声明)
- **票池是精选 30 只, 不是真实"成交额前 300"筛选** - yfinance 无 screener; RS 排名只在 30 只内部。
- **预警是单序列阈值代理, 不是真突破/回踩** - RSI 突破70 ≈ 动量代理; SPY/QQQ 日跌>1% ≈ 报告触发代理。真信号需复合形态检测。
- **仅日K, 无 2h K线** - 利弗莫尔"2h 创20日新高"未实现。
- **无 HV 分位** - `volstd20` 是 20 日波动率绝对值, 不是"历史 40% 分位以下"。
- **无 AI 研报 / 无多渠道** - 仅飞书; 钉钉/企微/Telegram 缺 env key。
- **无次新股通道** - `entities` 无上市日期字段。
- **无 cron** - 刷新手动 (重跑 fetch + run_indicator + build 脚本)。

### 手动刷新流程
```bash
# 1. 刷新 32 只日K (重跑 fetch 脚本, 或对每只 yf.Ticker(sym).history(period='1y'))
# 2. 重算指标 (run_indicator.py 对每条规则, 或循环)
# 3. 重建看板
uv run python fd-daas-mcp/dashboard-mcp/dashboards/build_us_leaders_dashboard.py
```

---

## Phase 3+: 自定义工程路线图

按依赖顺序排列。每项标注: 依赖 / 改动点 / 验收。

### 3.1 2h K线数据管线 (利弗莫尔突破前置)
- **依赖**: 无 (数据层基础)
- **改动**: 新增 `fetch_us_intraday.py`
  - yfinance 60m: `yf.Ticker(sym).history(period='730d', interval='60m')` (60m 最长 730 天)
  - 合成 2h: 把每 2 根 60m 合并 (Open=第一根Open, High=max, Low=min, Close=第二根Close, Volume=sum), 对齐美股交易时段 (9:30-16:00 ET, 6.5h = 3 根 2h + 半根)
  - 存 `scraw_<sym>_2h` 表 (date-time key)
- **验收**: SPY 2h 表有 ~3900 行 (2年×~1300根2h), 能算 2h 的 20 周期新高

### 3.2 自定义指标 ops (扩展 run_indicator.py)
- **依赖**: 3.1 (2h 数据)
- **改动**: 在 `fd-daas-based-data-fetch/scripts/run_indicator.py` 的 OPS 注册新 op:
  - `atr` (params: window=14) - 真实波幅 TR=max(H-L, |H-prevC|, |L-prevC|) 的 SMA
  - `hv_percentile` (params: window=20, lookback=252) - rolling_std(log_return, window) 在 lookback 窗口内的百分位 → 解决"HV 处历史 40% 分位以下"
  - `cross_sectional_rank` - 跨表排名 (需特殊处理: 读多个 scraw 表, 算同期 pct_change, 排名) → 解决 7/20/60/120 日 RS 排名(可存储而非看板实时算)
  - `breakout_signal` (params: window=20) - Close > rolling_max(High, window).shift(1) → 1/0 信号序列
  - `pullback_signal` - Close 回踩 MA5/10/20 后放量站上 → 1/0 (多条件复合)
  - `vcp` - 波动率收缩形态 (连续 N 段 rolling_std 递减)
  - `atr_contraction` (params: fast=5, slow=5, prev_offset=5) - 最近5日 ATR vs 上市前5日 ATR 下降>50% (次新股用)
- **验收**: `run_indicator.py --list-ops` 列出新 op; 对 NVDA 算 `breakout_signal` 得到 0/1 序列

### 3.3 形态检测引擎 (真突破 / 真回踩 / VCP)
- **依赖**: 3.1, 3.2
- **改动**: 新增 `signal_engine.py`
  - **利弗莫尔平台突破**: 2h Close 创 20 周期新高 AND hv_percentile(7d/20d/60d 任一) ≤ 40
  - **欧奈尔向导股回踩**: 大盘(SPYP/QQQ 2h 阴线≥50%) AND 龙头池跌幅最小 Top2 AND 回踩 MA5/10/20 后放量站上
  - **VCP**: rolling_std 连续 3 段递减且最后段 < 首段 30%
  - 输出信号序列写入 `observations` (indicator=`<SYM>_breakout` / `_pullback` / `_vcp`, 值 0/1)
- **验收**: 信号序列非全 0; 回测最近 1 年能看到合理触发点

### 3.4 预警升级 (复合信号 → 飞书 + 多渠道)
- **依赖**: 3.3
- **改动**:
  - 替换 Phase 2 的 RSI 代理规则为真信号规则: `source_table=observations`, `series_filter={indicator:<SYM>_breakout}`, `condition=crosses_above(0.5)`
  - 配置多渠道 env (`.env`): `ALERTS_DINGTALK_WEBHOOK_URL`, `ALERTS_WECOM_WEBHOOK_URL`, `ALERTS_TELEGRAM_BOT_TOKEN` + chat_id
  - 每条信号含: 名称/买点类型/时间/价格/止损位/仓位建议/AI一句话点评(点评由 3.5 注入 message_template 或单独生成)
- **验收**: 触发一次信号, 三渠道都收到

### 3.5 AI 研究报告生成器 [用户决定: 不做, 跳过]
- **状态**: 已移出范围 (用户 2026-07-16 决定 "不用管")。leader-mcp/CrewAI 层保留, 但本策略不接入研报生成。

### 3.6 次新股绿色通道
- **依赖**: 3.1, 3.2 (atr_contraction)
- **改动**:
  - `entities.metadata` JSON 加 `listing_date` 字段 (或新列); 用 yfinance 的 `Ticker.info['firstTradeDate']` / IPO 日期回填
  - 新增 `us_new_stocks` collection, rule_script: 上市天数 T≤45 AND 日均成交额≥2000万美元 AND ≥池A 7日均额×0.2
  - 动量保送: 上市以来累计涨幅 Top5 → 进核心池 X
  - 指标修正: T<N 时窗口截断为 T; 用 atr_contraction 代替 HV 分位
- **验收**: collection 能筛出当前 T≤45 的新股; 对其中 1 只算 atr_contraction

### 3.7 真实"成交额前 300"筛选器
- **依赖**: 无 (但解锁 3.6 的相对门槛)
- **改动**: yfinance 无全市场 screener, 需引入数据源:
  - 方案 A: 用 `stockanalysis.com` / finviz 的 CSV/接口 (需反爬, 用 fd-daas-scrapling-official skill)
  - 方案 B: 用 S&P 500 + NASDAQ 100 + Russell 1000 成分股名单 (静态, 季度更新) 作为近似"前 300"universe, 然后按成交额排序
  - 方案 C: akshare 的美股接口 (如 `ak.stock_us_spot_em`) 拿成交额排名
  - 筛选后写入 `scraw_us_top300_daily` 或动态更新 `us_leadership_pool` 的 rule_script
- **验收**: 能产出近 N 日平均成交额前 300 名单; `us_leadership_pool` 可由 rule_script 动态派生而非硬编码 30 只

### 3.8 cron 自动刷新
- **依赖**: 3.1-3.5 稳定后
- **改动**: 用 cron-mcp (已并入 fd-daas-mcp) 注册:
  - 04:30 Asia/Shanghai fetch 32+ 只日K + 2h
  - 04:45 重算所有指标 + 信号
  - 05:00 重建看板
  - 信号引擎实时(或每 2h)轮询 → 触发预警
- **验收**: 连续 3 天自动刷新无人工干预

---

## 优先级建议
1. **3.7 (真实 top300)** + **3.2 (custom ops: breakout_signal, hv_percentile)** - 最大策略保真度提升
2. **3.1 (2h)** + **3.3 (形态引擎)** - 解锁利弗莫尔真突破
3. **3.4 (多渠道)** - 低成本, 立即受益
4. **3.5 (AI 研报)** - 差异化价值
5. **3.6 (次新股)** - 独立轨道, 可并行
6. **3.8 (cron)** - 收尾自动化

## 决策点 (已决定, 2026-07-16)
- **3.7 数据源**: 美股。用 S&P 500 成分股(GitHub raw `datasets/s-and-p-500-companies`)作候选 universe, yfinance 1y 日K算 20 日均成交额, 排序取 top 300。✅ 已实现 (`fd-daas-mcp/dashboard-mcp/dashboards/screen_us_top300.py` -> `scraw_us_top300_screen`)。注: 候选 universe 是 S&P 500 (~503), 已覆盖真实 top-300-by-turnover (皆大盘); 若需全市场(含中盘高换手)可扩 NASDAQ 100 / Russell 1000。
- **3.5 AI 研报**: 不做, 已移出范围。
- **3.8 信号轮询**: 1 分钟一次 (target)。**需 3.1(2h)+3.3(信号引擎) 完成后才有意义** - 日K代理阶段数据每日才变, 1 分钟轮询会空转; 当前保持每日刷新。wire 时机: 2h 信号落地后, 用 cron-mcp 注册 `* * * * *` 任务调 alerts 引擎评估全量规则。
