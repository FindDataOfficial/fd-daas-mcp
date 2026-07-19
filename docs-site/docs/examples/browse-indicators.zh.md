# 浏览指标

DAAS 内置数百条覆盖公司与国家的预置指标规则，平台随数据源增加可扩展到上千条。本示例展示如何按实体、数据源、算子浏览。

## 什么是"指标"？

一条**指标规则**（`indicator_rules` 表的一行）把一个*源表* + 一个*数学算子* + *参数* 绑定到一个*指标名*，计算出的序列落到 `observations`。例如 `SPY_ma5` = 对 `scraw_spy_daily.close` 做 `sma`、`window=5`。

## 通过 SQL 浏览

从仓库根目录：

```bash
# 有多少条指标规则？
sqlite3 daas.db "SELECT count(*) FROM indicator_rules;"

# SPY 的指标
sqlite3 daas.db "SELECT name, op, indicator_name, source_table FROM indicator_rules WHERE name LIKE 'SPY_%';"

# observations 中不同的指标
sqlite3 daas.db "SELECT count(DISTINCT indicator) FROM observations;"

# 某指标的最新值
sqlite3 daas.db "SELECT date, value FROM observations WHERE indicator='SPY_ma5' ORDER BY date DESC LIMIT 5;"
```

## 按实体类型浏览

实体是股票或国家：

```bash
sqlite3 daas.db "SELECT entity_type, count(*) FROM entities GROUP BY entity_type;"
# stock|5575   country|60
```

所以指标横跨 **5,575 只股票** 和 **60 个国家** -- 既有公司级（`SPY_ma5`、`AAPL_rsi14`），也有国家/宏观级（CPI、GDP、国债收益率，来自 `cnstats` / `worldbank`）。

## 通过 MCP 浏览

把 MCP 客户端指向 `fd-daas-mcp`，使用 `daas_*` 工具：

- `daas_list_indicators` -- 所有指标规则（含有效分数）。
- `daas_list_indicator_ops` -- 固定数学算子目录 + 所需参数。
- `daas_get_series_latest` -- 某序列最新 N 行。
- `daas_calculate_indicator` -- 对源表做临时计算**不落库**（适合"算出来看看"）。

## 通过技能浏览

在 Claude Code 里：

> 列出所有 RSI 指标并显示每个的最新值。

`fd-daas-fetch-data` 技能会解析目录并读取 `observations`。

## 可用算子

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py --list-ops
```

| 算子 | 参数 | 说明 |
| --- | --- | --- |
| `sma` / `ema` | `window` | 简单/指数移动平均。 |
| `rsi` | `window` | 相对强弱指数。 |
| `pct_change` / `log_return` / `diff` | - | 变化序列。 |
| `rolling_std` / `rolling_min` / `rolling_max` | `window` | 滚动统计。 |
| `zscore` | `window` | 滚动 z-score。 |
| `ratio` / `level` | - | 比率 / 水平序列。 |

## 下一步

把关心的指标放进一个集合：[创建集合](create-collections.md)。
