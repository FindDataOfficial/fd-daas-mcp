# Browse Indicators

DAAS ships hundreds of prebuilt indicator rules across companies and countries,
and the platform scales to thousands as you add datasources. This example shows
how to browse them by entity, source, and op.

## What is an "indicator"?

An **indicator rule** (row in `indicator_rules`) binds a *source table* + a
*math op* + *params* to an *indicator name*, and its computed series lands in
`observations`. For example, `SPY_ma5` = `sma` over `scraw_spy_daily.close`
with `window=5`.

## Browse via SQL

From the repo root:

```bash
# How many indicator rules exist?
sqlite3 daas.db "SELECT count(*) FROM indicator_rules;"

# Indicators for SPY
sqlite3 daas.db "SELECT name, op, indicator_name, source_table FROM indicator_rules WHERE name LIKE 'SPY_%';"

# Distinct computed indicators in observations
sqlite3 daas.db "SELECT count(DISTINCT indicator) FROM observations;"

# Latest values for an indicator
sqlite3 daas.db "SELECT date, value FROM observations WHERE indicator='SPY_ma5' ORDER BY date DESC LIMIT 5;"
```

## Browse by entity type

Entities are stocks or countries:

```bash
sqlite3 daas.db "SELECT entity_type, count(*) FROM entities GROUP BY entity_type;"
# stock|5575   country|60
```

So indicators span **5,575 stocks** and **60 countries** - company-level
(`SPY_ma5`, `AAPL_rsi14`) and country/macro-level (CPI, GDP, treasury yields
from `cnstats` / `worldbank`).

## Browse via MCP

Point your MCP client at `fd-daas-mcp` and use the `daas_*` tools:

- `daas_list_indicators` - all indicator rules (with effective scores).
- `daas_list_indicator_ops` - the fixed math-op catalog + required params.
- `daas_get_series_latest` - latest N rows of a series.
- `daas_calculate_indicator` - ad-hoc compute over a source table **without
  persisting** (great for "what would this look like?").

## Browse via skill

In Claude Code:

> List all RSI indicators and show the latest value for each.

The `fd-daas-fetch-data` skill resolves the catalog and reads `observations`.

## Available ops

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py --list-ops
```

| Op | Params | Description |
| --- | --- | --- |
| `sma` / `ema` | `window` | Simple/exponential moving average. |
| `rsi` | `window` | Relative strength index. |
| `pct_change` / `log_return` / `diff` | - | Change series. |
| `rolling_std` / `rolling_min` / `rolling_max` | `window` | Rolling stats. |
| `zscore` | `window` | Rolling z-score. |
| `ratio` / `level` | - | Ratio / level-of-series. |

## Next

Group the indicators you care about into a collection:
[Create Collections](create-collections.md).
