# Vocabulary extension — commodities futures

Eval `vocabulary-extension-commodities` (eval 2, **without_skill** condition).
Pre-extended the canonical indicator vocabulary with three commodities-futures
columns (`settle_price`, `open_interest`, `warehouse_stocks`) and verified the
matcher resolves them against a throwaway datasource.

## What I did

1. **Found the existing canonical-indicator concept.** The repo already has a
   canonical indicator vocabulary (not something I had to design from scratch):
   - `references/canonical-indicators.md` — the human-readable source of truth
     (a markdown table; 34 seed rows covering market-data / fundamentals / macro /
     alternative).
   - `scripts/setup_indicator_vocabulary.py` — parses the markdown and upserts
     each row into a `canonical_indicators` table (declared inline on the shared
     `Base.metadata`, created via `create_all`).
   - `scripts/match_columns_to_indicators.py` — the matcher. For each of a
     source's `daas_function_columns` it tries exact (conf 1.0, confirmed) →
     alias (0.95, confirmed) → fuzzy ≥0.85 (PROPOSED, needs review), and upserts
     the result into `column_indicator_mappings` on
     `(source, function_name, column_name)`.
2. **Designed 3 new canonical indicators** for the commodities domain. Each is a
   recurring, cross-source field (every futures exchange reports settle/OI/
   warehouse stocks), so minting a canonical name is justified (per the
   vocabulary's own "don't mint one-offs" rule):
   - `settle_price` — Settlement price; unit `currency`, semantic_type `price`,
     category `market-data`; aliases `settlement_price, settlement, settle,
     结算价, 结算, Settle`.
   - `open_interest` — Open interest; unit `count`, semantic_type `count`,
     category `market-data`; aliases `openinterest, open interest, OI, 持仓量,
     持仓, OpenInterest`.
   - `warehouse_stocks` — Warehouse stocks (physical commodity inventory); unit
     `count`, semantic_type `count`, category `alternative`; aliases
     `warehouse_inventory, inventory, stocks, 库存, 仓单库存, warehouse_stock`.
3. **Ran the full pipeline against a throwaway DB** (`run_eval.py`, in this
   `outputs/` dir), reusing the REAL setup parser + REAL matcher logic (in-process
   imports of the skill scripts — functionally identical to running them as
   `python script.py`):
   - Bootstrapped daas tables via `daas_database.Database` (creates all 13+ daas
     tables; `canonical_indicators`/`column_indicator_mappings` created by the
     inline models' `create_all`).
   - Seeded the 34 existing indicators from `canonical-indicators.md`.
   - Inserted the 3 new commodity indicators → 37 rows total.
   - Registered a throwaway source `commodities_futures` + function
     `futures_daily` + the 3 columns (`settle_price`, `open_interest`,
     `warehouse_stocks`, all `REAL`).
   - Ran the matcher: all 3 columns matched **exact** (conf 1.0, confirmed=1)
     because the canonical names match the column names verbatim. No fuzzy
     proposals, no unmatched columns, no spurious canonical names invented.

## Vocabulary / mapping approach (documented)

The vocabulary is the existing repo concept (found in the
`fd-datasource-mcp-creator` skill). Source of truth = the markdown table; the
setup script parses + upserts into `canonical_indicators`; the matcher
normalizes names/aliases (`re.sub(r"[\W_]+", "", s.lower())` — strips
underscores/punctuation, keeps CJK) and matches exact → alias → fuzzy. I did
**not** design a new concept; I extended the existing one. Canonical names were
chosen to match the column names verbatim so the columns resolve at the
highest confidence tier (exact, auto-confirmed) rather than as fuzzy proposals.

## DB rows (throwaway DB)

`DAAS_DATABASE_URL=sqlite:////tmp/fd-dsc-eval/eval2-without/commodities.db`

| table | rows of interest |
|---|---|
| `sources` | 1: `commodities_futures` (id=1, enabled=1) |
| `daas_functions` | 1: `futures_daily` (source_id=1) |
| `daas_function_columns` | 3: `open_interest`, `settle_price`, `warehouse_stocks` (all REAL) |
| `canonical_indicators` | 37 (34 seeded + 3 new commodity rows) |
| `column_indicator_mappings` | 3, all confirmed: `open_interest→open_interest [exact 1.0]`, `settle_price→settle_price [exact 1.0]`, `warehouse_stocks→warehouse_stocks [exact 1.0]` |

## Verification output

```
[5] Matcher: 3 columns to match against 37 canonical indicators
  column               method   conf   confirmed  → indicator
  open_interest        exact    1.00   True       → open_interest
  settle_price         exact    1.00   True       → settle_price
  warehouse_stocks     exact    1.00   True       → warehouse_stocks
[6] RESULT: PASS — all 3 columns matched & confirmed
```

## Steps skipped / faked and why

- **Did NOT modify the real `references/canonical-indicators.md`.** The eval's
  "expected output" mentions adding rows to that file, but the task guardrails
  say "keep the real repo clean" / do not modify the real `mcp/daas.db` or
  `.mcp.json`. To respect the guardrails I inserted the 3 new rows directly into
  the throwaway DB's `canonical_indicators` table (the same end state the setup
  script would produce from an edited markdown) rather than editing the tracked
  skill reference file. The exact markdown rows I would have added are:

  ```
  | settle_price | Settlement price | currency | price | market-data | settlement_price, settlement, settle, 结算价, 结算, Settle | Official daily settlement price for a futures/derivatives contract. |
  | open_interest | Open interest | count | count | market-data | openinterest, open interest, OI, 持仓量, 持仓, OpenInterest | Number of outstanding (unsettled) derivative contracts. |
  | warehouse_stocks | Warehouse stocks | count | count | alternative | warehouse_inventory, inventory, stocks, 库存, 仓单库存, warehouse_stock | Physical inventory of a commodity held in registered warehouses. |
  ```

  To make these permanent, append them to the table in
  `.claude/skills/fd-datasource-mcp-creator/references/canonical-indicators.md`
  and re-run `setup_indicator_vocabulary.py` against the real `mcp/daas.db`.
- **In-process matcher invocation instead of subprocess.** The matcher was run
  by importing `match_columns_to_indicators._match` / `_load_canonical` and
  driving the same upsert SQL in one process (vs. spawning
  `python match_columns_to_indicators.py --source …`). Same code path, same DB
  writes; chosen for reliability of env-var/cwd wiring under the daas-mcp venv.
  The `setup_indicator_vocabulary.py` parser (`_parse_seed`) was likewise
  reused in-process.
- **Did NOT modify the real `mcp/daas.db` or `.mcp.json`.** Confirmed: the real
  DB has no `canonical_indicators` table and its mtime is unchanged; all
  writes went to the throwaway DB only.
- **No real MCP server started / no `.mcp.json` edit.** The source/function/
  column registration was done via direct ORM rows rather than the
  `create_datasource` tool, since the goal was to exercise the matcher (a read
  over `daas_function_columns`), not to validate the datasource-creation tool.
