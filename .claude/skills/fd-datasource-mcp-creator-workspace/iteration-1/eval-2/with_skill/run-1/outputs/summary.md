# Vocabulary extension — commodities futures source

Pre-extended the canonical indicator vocabulary for an upcoming commodities
futures source whose tables expose `settle_price`, `open_interest`, and
`warehouse_stocks`. None were in the seed vocabulary. The throwaway DB lives at
`/tmp/fd-dsc-eval/eval2-with/commodities.db`; the real `mcp/daas.db`,
`.mcp.json`, and `mcp/models/models.py` were **not** touched.

## The 3 new canonical-indicator rows

Added to the seed table (appended after `put_call_ratio`):

| name | label | unit | semantic_type | category | aliases | description |
|---|---|---|---|---|---|---|
| settle_price | Settlement price | currency | price | market-data | 结算价, Settlement, Settle, settlement_price, SettlementPrice | Daily settlement price of a futures contract. |
| open_interest | Open interest | count | count | market-data | 持仓量, 持仓, OpenInterest, open interest, OI | Number of outstanding (unsettled) futures/options contracts. |
| warehouse_stocks | Warehouse stocks | count | count | alternative | 库存, 仓单, WarehouseStocks, warehouse_inventory, inventory | Quantity of a commodity held in registered warehouses (commodity-specific physical units). |

Notes on the choices:

- `settle_price` — `currency`/`price` mirrors `close`/`open`; a settlement
  price is the exchange-fixed daily mark for a futures contract. Aliases cover
  the Chinese `结算价` and common `Settlement`/`Settle` column spellings.
- `open_interest` — unit `count` + semantic_type `count` (a count of
  outstanding contracts, structurally like `shares_outstanding`, not a traded
  volume). Aliases cover `持仓量`/`持仓` (akshare/SHFE), `OpenInterest`,
  `open interest`, `OI`.
- `warehouse_stocks` — category `alternative` (inventory/supply data, not
  standard exchange price/volume). Unit `count` since the physical unit is
  commodity-specific (tons / barrels / ounces); the description notes this.
  Aliases cover `库存`/`仓单` (SHFE/LME), `WarehouseStocks`,
  `warehouse_inventory`, `inventory`.

## Matcher result

Registered a throwaway source `commodities_test` + function `futures_daily`
with the 3 columns (direct SQL against the throwaway DB). Ran:

```
DAAS_DATABASE_URL=sqlite:////tmp/fd-dsc-eval/eval2-with/commodities.db \
  uv run --directory /Users/chengsishi/code/cli-anything/mcp/daas-mcp python \
  .claude/skills/fd-datasource-mcp-creator/scripts/match_columns_to_indicators.py \
  --source commodities_test
```

Output: `commodities_test: 3 columns — did map 3 (3 confirmed, 0 proposed), 0 unmatched.`

Per-column result (from `column_indicator_mappings`):

| column | indicator | method | confidence | confirmed |
|---|---|---|---|---|
| settle_price | settle_price | exact | 1.0 | yes |
| open_interest | open_interest | exact | 1.0 | yes |
| warehouse_stocks | warehouse_stocks | exact | 1.0 | yes |

All three matched `exact` (lowercased, alnum-stripped column == canonical name)
→ confidence 1.0 → auto-confirmed (`confirmed=1`). No fuzzy proposals, no
unmatched columns. This is the cleanest possible outcome and follows from
naming the canonical indicators exactly what the source's columns are called;
the aliases are the cross-source hooks (e.g. a future SHFE source exposing
`结算价` would match `settle_price` via `alias`, conf 0.95).

## Flow followed

1. **Bootstrap throwaway DB.** Created the eval dir + DB and ran
   `setup_indicator_vocabulary.py` with
   `DAAS_DATABASE_URL=sqlite:////tmp/fd-dsc-eval/eval2-with/commodities.db`.
   This created all daas tables + the 2 indicator tables and seeded the
   34-indicator vocabulary. The real `mcp/models/models.py` Step-0 paste was
   skipped (the script's inline model declarations create the tables on the
   shared `Base.metadata`).
2. **Copy + edit the .md.** Copied
   `references/canonical-indicators.md` →
   `/tmp/fd-dsc-eval/eval2-with/canonical-indicators.md` and appended the 3 new
   rows (so the real `.md` source of truth stays untouched during this eval).
3. **Re-seed from the copy.** Wrote a one-off snippet
   (`/tmp/fd-dsc-eval/eval2-with/parse_and_upsert.py`) that mirrors
   `setup_indicator_vocabulary.py`'s parser + upsert but reads the *copy*.
   Ran it against the throwaway DB: `37 canonical indicators: 3 new, 34
   updated`.
4. **Register throwaway source + function + columns.** Direct SQL against the
   throwaway DB: one `sources` row (`commodities_test`), one `daas_functions`
   row (`futures_daily`), three `daas_function_columns` rows
   (`settle_price`/`open_interest`/`warehouse_stocks`).
5. **Run the matcher.** `match_columns_to_indicators.py --source
   commodities_test` → all 3 matched `exact`, conf 1.0, auto-confirmed.

The edited `canonical-indicators.md` (with the 3 new rows) is copied into this
`outputs/` dir alongside this summary.
