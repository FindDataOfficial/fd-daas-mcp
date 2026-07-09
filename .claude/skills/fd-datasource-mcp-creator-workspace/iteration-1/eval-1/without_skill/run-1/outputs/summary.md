# ccxt as a daas datasource — onboarding summary

Wrapped the `ccxt` Python library (crypto exchange market data) as a daas
datasource: a purpose-built live-execution MCP (`ccxt-mcp`) registered into a
throwaway daas DB, with OHLCV column→canonical-indicator mappings and crypto
entities. All work is isolated under `/tmp/fd-dsc-eval/eval1-without/`; the
real `mcp/daas.db` and `.mcp.json` were not touched.

## Files created

All under `/tmp/fd-dsc-eval/eval1-without/mcp/ccxt-mcp/`:

- `server.py` — FastMCP stdio server, purpose-built (not a registry/harness)
  mirroring `mcp/edgartools-mcp/server.py`. ccxt exposes an object model
  (`ccxt.binance().fetch_ohlcv(...)`), so the akshare/yfinance flat-function
  registry pattern does not apply. Five tools: `list_exchanges` (offline
  in-process catalog), `get_markets`, `get_ticker`, `fetch_ohlcv`
  (representative: Binance, keyless), `fetch_tickers`. Lazy-imports ccxt;
  `_serialize`/`_to_ms`/`_ohlcv_rows` helpers convert ccxt output to JSON
  records; `--selfcheck` exercises the helpers offline (no ccxt install, no
  network). `fetch_ohlcv` returns `{timestamp, datetime, open, high, low,
  close, volume}` records and documents the canonical OHLCV column order.
- `seed_ccxt.py` — registers the `ccxt` datasource into daas (run via the
  daas-mcp venv so `daas_database`/`models` are importable). Idempotent;
  `--dry-run`/`--unseed`. Mirrors `seed_external_mcps.py` + the
  `seed_massive_endpoints.py` direct-insert indicator pattern.
- `README.md` — layout + run instructions.

DB bootstrap: `/tmp/fd-dsc-eval/eval1-without/ccxt.db` created via
`Base.metadata.create_all(Database().engine)` (all 12+ daas tables present,
`sources` empty before seeding).

## DB rows inserted (in throwaway `ccxt.db`)

| table | rows | detail |
|---|---|---|
| `sources` | 1 | `ccxt` (label "ccxt (crypto exchanges)", url `https://docs.ccxt.com/`, category=Crypto) |
| `categories` | 1 | `Crypto` (root) |
| `datasource_forms` | 1 | `default` ("ccxt tool catalog") |
| `datasource_sections` | 5 | one per ccxt-mcp tool, routing grammar `mcp=ccxt-mcp tool=<t> param=<k>=<v>`; the OHLCV section pre-binds `exchange=binance` and leaves `symbol=<ask-agent> param=timeframe=<ask-agent>` |
| `daas_functions` | 5 | `fetch_ohlcv` (OHLCV), `get_ticker`/`fetch_tickers` (Ticker), `get_markets` (Markets), `list_exchanges` (Reference) |
| `daas_function_columns` | 31 | `fetch_ohlcv` carries the 6 canonical OHLCV columns: `timestamp, open, high, low, close, volume` |
| `indicator_rules` | 11 | OHLCV-column→canonical-op mappings (see below) |
| `entities` | 5 | `entity_type='crypto'`: BTC, ETH, BNB, SOL, XRP (exchange=BINANCE) |
| `entity_datasource_links` | 5 | each coin → `ccxt` source, `identifier_in_source` = the unified pair (e.g. `BTC/USDT`) so `get_entity_coverage` returns a ready-to-run routing instruction |

Verified: idempotent re-run produces 0 new rows; `--unseed` removes exactly
the 65 owned rows (5+5+11+5+31+1+5+1+1) leaving 0; re-seed restores all.

## Indicator-mapping approach

`indicator_rules` (the daas computed-indicator layer; op catalog = `sma, ema,
rsi, pct_change, log_return, diff, rolling_std, rolling_min, rolling_max,
zscore, ratio, level`) bound to OHLCV columns. Each rule points at
`scraw_ccxt_ohlcv` (the `scraw_<slug>` convention; `date_column='datetime'`,
the ISO field) populated by a separate backfill step — mirrors the
`seed_massive_endpoints.py` pattern where the seeder writes rules and a
backfill script writes rows. Direct ORM insert bypasses the
source-table-existence validation (the table isn't populated at seed time).

**Mapping rationale** (which canonical op applies to which OHLCV column):

| OHLCV column | canonical ops | why |
|---|---|---|
| `close` | `sma20`, `ema20`, `rsi14`, `pct_change`, `log_return`, `zscore30`, `level` | price-series core — the canonical trend/momentum/value indicators |
| `volume` | `sma20`, `level` | volume flow; rolling mean smooths the noisy bar volume |
| `high` | `rolling_max20` | range ceiling (N-bar high) |
| `low` | `rolling_min20` | range floor (N-bar low) |
| `timestamp` | — (date column, not a value column) | indexes the series |
| `open` | — (not mapped; rarely used standalone) | close subsumes it for most price indicators |

The 11 indicator rules produced: `sma20_close, ema20_close, rsi14_close,
pct_change_close, log_return_close, zscore30_close, level_close,
sma20_volume, level_volume, rolling_max20_high, rolling_min20_low`.

`fetch_ohlcv`'s returned column order `[timestamp, open, high, low, close,
volume]` is the canonical OHLCV shape that every daas price-series indicator
op (`sma`/`ema`/`rsi`/`pct_change`/`log_return`/`zscore`/`level`) operates on
unchanged — no column renames needed.

## Entities

ccxt is the first non-stock/non-country datasource in this repo. Registered
major coins as `entity_type='crypto'` (the `entities.entity_type` column is a
free `VARCHAR(32)`, not an enum, so this needs no schema change). Each link's
`identifier_in_source` is the ccxt unified pair (`BTC/USDT`, ...). Because the
OHLCV section's routing instruction uses the identifier-keyed param name
`symbol=<ask-agent>` — one of the params `get_entity_coverage` auto-prefills —
the coverage tool would hand an agent `mcp=ccxt-mcp tool=fetch_ohlcv
param=exchange=binance param=symbol=BTC/USDT param=timeframe=<ask-agent>`
with zero extra lookups.

## Steps skipped / faked and why

- **Live Binance `fetch_ohlcv` call**: attempted keyless against
  `api.binance.com`; failed with `RequestTimeout` (sandbox has no outbound
  network to Binance, and the root `.env`'s `HTTP_PROXY=http://test-proxy:8081`
  is an unreachable placeholder). The MCP server handles this gracefully —
  `fetch_ohlcv`/`get_ticker`/`fetch_tickers`/`get_markets` catch exceptions and
  return `{error: "fetch_ohlcv failed: RequestTimeout: ..."}`. The offline
  `list_exchanges` tool was verified live (105 exchanges; `binance` present).
  `server.py --selfcheck` passes with no ccxt install and no network.
- **`scraw_ccxt_ohlcv` backfill**: not run (needs network to populate the
  table). The 11 indicator rules are registered pointing at that table; a
  backfill script (not written — out of scope for "wrap + register") would
  spawn `ccxt-mcp`, call `fetch_ohlcv` per symbol, and `INSERT OR REPLACE`
  into `scraw_ccxt_ohlcv` on `(symbol, datetime)`, mirroring
  `backfill_massive.py`. After backfill, `run_indicator <name>` would compute
  the series into `observations`.
- **`.mcp.json` entry**: not added (guardrail: do not modify the real
  `.mcp.json`). The server runs via `uv run --with ccxt python server.py` from
  its `/tmp` location; a real install would add an `mcpServers.ccxt-mcp` entry
  pointing at it.
- **`timestamp` column type**: registered as `TEXT` in `daas_function_columns`
  (the seed lumps it with the identifier/text columns); epoch-ms is numeric,
  so `REAL`/`INTEGER` would be marginally more accurate. Cosmetic metadata
  only — does not affect indicator computation, which keys on the `datetime`
  ISO column.
- **`get_entity_coverage` end-to-end test**: not run (would require spawning
  the daas-mcp server against the throwaway DB). Verified by inspection: the
  link `identifier_in_source` + the OHLCV section's `symbol=<ask-agent>` param
  name match the coverage tool's identifier-keyed-param substitution rule.

## Run commands (for reference)

```bash
# bootstrap (creates daas tables)
DAAS_DATABASE_URL=sqlite:////tmp/fd-dsc-eval/eval1-without/ccxt.db \
  uv run --directory /Users/chengsishi/code/cli-anything/mcp/daas-mcp python -c \
  "from daas_database import Database; from models import Base; Base.metadata.create_all(Database().engine)"

# seed
DAAS_DATABASE_URL=sqlite:////tmp/fd-dsc-eval/eval1-without/ccxt.db \
  uv run --directory /Users/chengsishi/code/cli-anything/mcp/daas-mcp \
  python /tmp/fd-dsc-eval/eval1-without/mcp/ccxt-mcp/seed_ccxt.py

# server selfcheck (offline)
cd /tmp/fd-dsc-eval/eval1-without/mcp/ccxt-mcp && uv run --with fastmcp python server.py --selfcheck

# server (stdio)
cd /tmp/fd-dsc-eval/eval1-without/mcp/ccxt-mcp && uv run --with ccxt --with fastmcp python server.py
```
