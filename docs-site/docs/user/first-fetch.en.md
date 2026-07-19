# First Fetch in 5 Minutes

This walkthrough fetches real data and computes a real indicator, end to end,
using the **skill path**. You will fetch SPY daily prices and confirm the
prebuilt `SPY_ma5` (5-day simple moving average) indicator.

## Prerequisites

- You have run `uv sync` (see [Install & Deploy](install.md)).
- The repo-root `daas.db` exists (it ships with the repo).

## 1. Confirm the entity exists

DAAS already knows about thousands of entities. Check that SPY is registered:

```bash
sqlite3 daas.db "SELECT id, code, name, entity_type FROM entities WHERE code='SPY' OR ticker='SPY' LIMIT 5;"
```

If SPY is not present, you can search/resolve it through the
`fd-daas-fetch-data` skill or the `daas_search_entities` MCP tool.

## 2. Resolve the fetch shape

The dispatch layer maps each source prefix to its Python library. SPY comes from
`yfinance`. See exactly how a function is called:

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve yfinance_ticker_history
```

This prints the import + call shape the skill uses - no guessing.

## 3. Fetch (through the skill)

In Claude Code, just ask:

> Fetch SPY daily OHLCV history (1 year) and persist it.

The `fd-daas-based-data-fetch` (or `fd-daas-fetch-data`) skill will:

1. Resolve the SPY entity + its `yfinance` identifier.
2. Call `yfinance` directly.
3. Persist the rows into a `scraw_<slug>` table (e.g. `scraw_spy_daily`) via
   `scripts/upsert.py` (which backs up `daas.db` first).

Confirm the data landed:

```bash
sqlite3 daas.db "SELECT date, close FROM scraw_spy_daily ORDER BY date DESC LIMIT 5;"
```

## 4. Compute a prebuilt indicator

`SPY_ma5` is already an `indicator_rules` row (5-day SMA of SPY closes). Compute
it into the `observations` table:

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py SPY_ma5
```

Read the result:

```bash
sqlite3 daas.db "SELECT date, value FROM observations WHERE indicator='SPY_ma5' ORDER BY date DESC LIMIT 5;"
```

## 5. List available ops

Want a different indicator? The math ops available:

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py --list-ops
```

Ops include `sma`, `ema`, `rsi`, `pct_change`, `log_return`, `diff`,
`rolling_std`, `rolling_min`, `rolling_max`, `zscore`, `ratio`, `level`.

## What just happened

- You used the **skill path**: skills called a Python library (`yfinance`)
  directly and wrote `daas.db` via `sqlite3`.
- Raw data went to `scraw_spy_daily`; the computed series went to `observations`.
- The MCP path sees the same data - try `daas_get_series_latest` or browse via
  the dashboard skill.

## Next

- Browse the full indicator catalog: [Browse Indicators](../examples/browse-indicators.md).
- Group entities/indicators: [Create Collections](../examples/create-collections.md).
- Turn a goal into a full study: [Create a Research](../examples/create-research.md).
