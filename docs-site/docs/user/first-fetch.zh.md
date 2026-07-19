# 5 分钟首次获取

本走查通过**技能路径**端到端获取真实数据并计算真实指标。你会获取 SPY 日线并确认预置的 `SPY_ma5`（5 日简单均线）指标。

## 前置条件

- 已运行 `uv sync`（见 [安装与部署](install.md)）。
- 仓库根目录的 `daas.db` 存在（随仓库一起提供）。

## 1. 确认实体存在

DAAS 已经知道数千个实体。检查 SPY 是否已注册：

```bash
sqlite3 daas.db "SELECT id, code, name, entity_type FROM entities WHERE code='SPY' OR ticker='SPY' LIMIT 5;"
```

若 SPY 不存在，可通过 `fd-daas-fetch-data` 技能或 `daas_search_entities` MCP 工具搜索/解析。

## 2. 解析获取形状

dispatch 层把每个源前缀映射到其 Python 库。SPY 来自 `yfinance`。看清楚一个函数如何被调用：

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve yfinance_ticker_history
```

它会打印技能使用的 import + 调用形状 -- 无需猜测。

## 3. 获取（通过技能）

在 Claude Code 里，直接说：

> 获取 SPY 近一年日线 OHLCV 并持久化。

`fd-daas-based-data-fetch`（或 `fd-daas-fetch-data`）技能会：

1. 解析 SPY 实体 + 其 `yfinance` 标识符。
2. 直接调用 `yfinance`。
3. 通过 `scripts/upsert.py` 把行写入 `scraw_<slug>` 表（如 `scraw_spy_daily`），写入前先备份 `daas.db`。

确认数据落库：

```bash
sqlite3 daas.db "SELECT date, close FROM scraw_spy_daily ORDER BY date DESC LIMIT 5;"
```

## 4. 计算预置指标

`SPY_ma5` 已经是一条 `indicator_rules` 行（SPY 收盘价的 5 日均线）。把它计算到 `observations` 表：

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py SPY_ma5
```

读取结果：

```bash
sqlite3 daas.db "SELECT date, value FROM observations WHERE indicator='SPY_ma5' ORDER BY date DESC LIMIT 5;"
```

## 5. 列出可用算子

想要别的指标？可用数学算子：

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py --list-ops
```

算子包括 `sma`、`ema`、`rsi`、`pct_change`、`log_return`、`diff`、`rolling_std`、`rolling_min`、`rolling_max`、`zscore`、`ratio`、`level`。

## 刚才发生了什么

- 你用了**技能路径**：技能直接调用 Python 库（`yfinance`）并通过 `sqlite3` 写入 `daas.db`。
- 原始数据进了 `scraw_spy_daily`；计算出的序列进了 `observations`。
- MCP 路径看到的是同一份数据 -- 试试 `daas_get_series_latest` 或用看板技能浏览。

## 下一步

- 浏览完整指标目录：[浏览指标](../examples/browse-indicators.md)。
- 分组实体/指标：[创建集合](../examples/create-collections.md)。
- 把一个目标变成完整研究：[创建研究](../examples/create-research.md)。
