# ccxt → daas datasource onboarding (with-skill)

Wrapped the `ccxt` Python library (unified crypto-exchange market data) as a
purpose-built daas datasource, registered it in a throwaway DB, registered
crypto-pair entities, and auto-mapped its OHLCV columns to the canonical
indicator vocabulary.

## Files created (all under /tmp/...)

- `/tmp/fd-dsc-eval/eval1-with/mcp/ccxt-mcp/server.py` — FastMCP purpose-built
  server (4 tools, lazy-imports ccxt, keyless for public data, Binance default).
  Copied to `outputs/server.py`.
- `/tmp/fd-dsc-eval/eval1-with/mcp/ccxt-mcp/pyproject.toml` — `ccxt>=4.0`,
  `fastmcp>=2.0`, `pandas`, `python-dotenv`; `requires-python>=3.10`.
- `/tmp/fd-dsc-eval/eval1-with/mcp/ccxt-mcp/.env.example` — documents
  `CCXT_DEFAULT_EXCHANGE` (default `binance`); notes public data is keyless.
- `/tmp/fd-dsc-eval/eval1-with/mcp/ccxt-mcp/.venv/` — `uv sync`'d; selfcheck
  passes; 4 tools register via `app.list_tools()`.
- `/tmp/fd-dsc-eval/eval1-with/seed_ccxt.sql` — source/functions/columns/form/
  sections seed (direct SQL against the throwaway DB).
- `/tmp/fd-dsc-eval/eval1-with/seed_ccxt_entities.sql` — 5 crypto_pair
  entities + links.

Throwaway DB: `/tmp/fd-dsc-eval/eval1-with/ccxt.db`
(`DAAS_DATABASE_URL=sqlite:////tmp/fd-dsc-eval/eval1-with/ccxt.db`). Bootstrapped
via `setup_indicator_vocabulary.py` — 34 canonical indicators seeded.

## Step-1 analysis

- **Package**: `ccxt` (pip-installable, `requires-python>=3.8` — server sets
  `>=3.10` to match the project floor). Unified object model: one `Exchange`
  class per exchange (binance, coinbase, okx, ...) with shared methods.
- **Data surface** (4 tools chosen, all keyless/public):

  | tool | ccxt call | returns |
  |---|---|---|
  | `fetch_ohlcv(symbol, timeframe='1d', limit=100, exchange='binance')` | `ex.fetch_ohlcv(...)` | `[[timestamp_ms, open, high, low, close, volume], ...]` — the representative call per the task |
  | `fetch_ticker(symbol, exchange='binance')` | `ex.fetch_ticker(...)` | dict: symbol, last, bid, ask, high, low, open, close, baseVolume, quoteVolume, ... |
  | `fetch_markets(exchange='binance', limit=200)` | `ex.load_markets()` | list of {symbol, base, quote, type, active} |
  | `fetch_order_book(symbol, limit=50, exchange='binance')` | `ex.fetch_order_book(...)` | {bids, asks, timestamp, nonce} |

- **Auth**: KEYLESS for public market data. No `CCXT_API_KEY` env var — the
  server has no `_require_auth` guard. Private endpoints (trading/balance) are
  intentionally not exposed.
- **Dependency**: ccxt, pandas, fastmcp, python-dotenv.

## Entity-domain decision

ccxt's domain is **crypto trading pairs**, not stocks or countries. The
`entities.entity_type` column is a free-form `String(32)` (the model comment
says `'stock'|'country'` but there's no CHECK constraint), so I registered a
new `entity_type='crypto_pair'` with `code` = the ccxt canonical pair symbol
(`BTC/USDT`). `entity_datasource_links.identifier_in_source` is set to the same
pair symbol — the exact string `fetch_ohlcv(symbol=...)` expects — so
`get_entity_coverage` can prefill the `symbol=` param in the routing
instruction. The `exchange` column is set to `binance` (the default exchange).

5 entities registered: BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT (the
top Binance spot pairs), all linked `coverage='full'` to ccxt.

## DB rows inserted (throwaway DB)

| table | rows | samples |
|---|---|---|
| `categories` | 2 | `Market-Data` (root), `Crypto` (child) |
| `sources` | 1 | `ccxt` / "ccxt (Crypto Exchanges)" / enabled=1 / category=Crypto |
| `daas_functions` | 4 | `fetch_ohlcv`, `fetch_ticker`, `fetch_markets`, `fetch_order_book` (category='Crypto') |
| `daas_function_columns` | 25 | 6 (ohlcv) + 10 (ticker) + 5 (markets) + 4 (order_book) |
| `datasource_forms` | 1 | `ccxt-default` (form_type='default') |
| `datasource_sections` | 4 | one per function, with routing grammar |
| `entities` | 5 | BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT (entity_type='crypto_pair') |
| `entity_datasource_links` | 5 | each pair → ccxt, identifier_in_source = pair symbol, coverage='full' |
| `column_indicator_mappings` | 10 | inserted by the matcher (see below) |

## Routing instructions (4 sections)

All pass the grammar regex `^mcp=\S+\s+tool=\S+(\s+param=[^=\s]+=\S+)*$`:

```
mcp=ccxt-mcp tool=fetch_ohlcv param=symbol=<ask-agent> param=timeframe=1d param=limit=100 param=exchange=binance
mcp=ccxt-mcp tool=fetch_ticker param=symbol=<ask-agent> param=exchange=binance
mcp=ccxt-mcp tool=fetch_markets param=exchange=binance param=limit=200
mcp=ccxt-mcp tool=fetch_order_book param=symbol=<ask-agent> param=exchange=binance
```

`<ask-agent>` marks params the dispatching agent must supply (the pair
symbol); `exchange`, `timeframe`, `limit` are pre-filled with sensible
defaults. The `entity_datasource_links.identifier_in_source` value plugs into
the `symbol=` slot when an agent dispatches via `get_entity_coverage`.

## Indicator-mapping result (Step 5)

Ran `match_columns_to_indicators.py --source ccxt` against the throwaway DB.

**25 columns → 10 mapped (all confirmed), 15 unmatched.**

### OHLCV → canonical indicators (the task's core question)

All 5 `fetch_ohlcv` columns map exactly (method=`exact`, confidence=1.0,
auto-confirmed):

| column | canonical indicator | method | confidence |
|---|---|---|---|
| `fetch_ohlcv.open` | `open` | exact | 1.0 |
| `fetch_ohlcv.high` | `high` | exact | 1.0 |
| `fetch_ohlcv.low` | `low` | exact | 1.0 |
| `fetch_ohlcv.close` | `close` | exact | 1.0 |
| `fetch_ohlcv.volume` | `volume` | exact | 1.0 |

So **ccxt's OHLCV columns map to the canonical indicators `open`, `high`,
`low`, `close`, `volume`** — the standard market-data price/volume set.

### Other matched columns (bonus)

| column | canonical indicator | method | confidence |
|---|---|---|---|
| `fetch_ticker.open` | `open` | exact | 1.0 |
| `fetch_ticker.high` | `high` | exact | 1.0 |
| `fetch_ticker.low` | `low` | exact | 1.0 |
| `fetch_ticker.close` | `close` | exact | 1.0 |
| `fetch_ticker.last` | `close` | alias | 0.95 |

`fetch_ticker.last` matched `close` via the canonical alias `Last` (last
traded price ~= close for a ticker snapshot). This is defensible — `last` and
`close` are the same value in ccxt's unified ticker structure — but worth a
human glance; it's already `confirmed=1` because alias matches auto-confirm.

### Unmatched columns (15) — correctly left unmapped

| column | why unmatched |
|---|---|
| `fetch_ohlcv.timestamp` | candle open time — an index, not an indicator |
| `fetch_ticker.symbol` | pair identifier, not an indicator |
| `fetch_ticker.bid` | no `bid_price` canonical name yet |
| `fetch_ticker.ask` | no `ask_price` canonical name yet |
| `fetch_ticker.baseVolume` | base-currency volume; name doesn't match `volume` |
| `fetch_ticker.quoteVolume` | quote-currency turnover; name doesn't match `turnover` |
| `fetch_markets.symbol` | metadata |
| `fetch_markets.base` | metadata |
| `fetch_markets.quote` | metadata |
| `fetch_markets.type` | metadata |
| `fetch_markets.active` | metadata |
| `fetch_order_book.bids` | order-book side, no canonical name |
| `fetch_order_book.asks` | order-book side, no canonical name |
| `fetch_order_book.timestamp` | snapshot time — an index |
| `fetch_order_book.nonce` | sequence number |

### Vocabulary-extension proposals (not applied — eval kept clean)

Two columns deserve canonical aliases if crypto becomes a recurring source
domain, but I did NOT extend `references/canonical-indicators.md` or re-run the
matcher (would touch the real repo's reference file). Listed here for review:

1. **`quoteVolume` → `turnover`** — ccxt's `quoteVolume` is the 24h traded
   value in the quote currency, which is exactly `turnover` (成交额). Adding
   `quoteVolume` to the `turnover` aliases would auto-match at 0.95.
2. **`baseVolume` → `volume`** — `baseVolume` is 24h volume in the base
   currency (e.g. BTC count for BTC/USDT), which is the same semantic as
   `volume` (成交量). Adding `baseVolume` to the `volume` aliases would
   auto-match at 0.95.
3. **`bid` / `ask`** — recurring across every crypto exchange; could earn
   canonical names `bid_price` / `ask_price` (category `market-data`).

Per the skill principle ("canonical names earn their place by recurring across
sources"), these are borderline — they recur across crypto exchanges but not
yet across the broader daas source set. Left as proposals.

## Steps skipped or faked

- **Live API call**: not made. `fetch_ohlcv('BTC/USDT')` against Binance timed
  out (`ccxt.base.errors.RequestTimeout` on `GET .../api/v3/exchangeInfo`) —
  no outbound network in this sandbox. The task explicitly said to use the
  documented shape `[timestamp, open, high, low, close, volume]` for column
  registration, so no live call was needed. The MCP server is built and would
  work given network; the selfcheck (offline serialization + exchange-init
  error paths) passes.
- **`.mcp.json` registration**: NOT done (guardrail). The entry you'd add to
  the real `.mcp.json`:
  ```json
  "ccxt-mcp": {
    "type": "stdio",
    "command": "uv",
    "args": ["run", "--directory", "/Users/chengsishi/code/cli-anything/mcp/ccxt-mcp", "python", "server.py"]
  }
  ```
  (pointing at the real `mcp/ccxt-mcp/` once the server is moved out of /tmp).
- **`mcp/models/models.py` edit**: skipped per guardrail — the two indicator
  tables (`canonical_indicators`, `column_indicator_mappings`) are declared
  inline on the shared `Base` by `setup_indicator_vocabulary.py`, so they
  exist in the throwaway DB without touching the real models file.
- **Usage skill** (skill Step 6): NOT created as a separate
  `.claude/skills/ccxt-usage/SKILL.md` to avoid polluting the real repo. The
  usage card is folded here: **tools** = `fetch_ohlcv`, `fetch_ticker`,
  `fetch_markets`, `fetch_order_book` (all keyless, default exchange binance);
  **examples** — `fetch_ohlcv(symbol='BTC/USDT', timeframe='1d', limit=100)`,
  `fetch_ticker(symbol='ETH/USDT')`, `fetch_markets(exchange='binance')`.
- **Direct SQL instead of daas-mcp tools**: the task permitted direct SQL
  against the throwaway DB (faster than spawning the daas-mcp server per
  call). The SQL mirrors the skill's `datasource-seed-template.py` shape;
  note the real `datasource_forms`/`datasource_sections` columns are
  `form_type`/`section_name` (not `name` — the template's `name=` is stale).
