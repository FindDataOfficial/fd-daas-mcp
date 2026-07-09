# meteostat datasource onboarding — summary

Eval: `unrelated-domain-restraint` (skill `fd-datasource-mcp-creator`, iteration 1, `with_skill`).

Goal: build a datasource from the `meteostat` Python library (weather station
time series), build the MCP, register the datasource, and map its columns to
canonical indicators where they fit — exercising the skill's "unrelated
domain" restraint branch (no false matches, no minted one-off canonical names).

## Files created

| path | purpose |
|---|---|
| `/tmp/fd-dsc-eval/eval3-with/mcp/meteostat-mcp/server.py` | purpose-built FastMCP server (3 tools: `station_daily`, `station_info`, `find_stations_nearby`). Copied to `outputs/server.py`. |
| `/tmp/fd-dsc-eval/eval3-with/mcp/meteostat-mcp/pyproject.toml` | uv project (`fastmcp`, `meteostat`, `pandas`, `python-dotenv`); `requires-python>=3.10` |
| `/tmp/fd-dsc-eval/eval3-with/mcp/meteostat-mcp/.env.example` | env doc — meteostat is KEYLESS; optional `METEOSTAT_CACHE_DIR` |
| `/tmp/fd-dsc-eval/eval3-with/mcp/meteostat-mcp/.venv/` | created via `uv sync` (meteostat + deps installed) |
| `/tmp/fd-dsc-eval/eval3-with/seed_meteostat.py` | seed script mirroring `references/datasource-seed-template.py` (uses real `Database`/ORM write path) |
| `/tmp/fd-dsc-eval/eval3-with/meteostat.db` | throwaway daas DB (bootstrap + seed + matcher all wrote here) |

`outputs/server.py` — the generated server, copied as required.

The real `mcp/daas.db`, `.mcp.json`, and `mcp/models/models.py` were **not**
modified. Step 0's `models.py` paste was skipped (the setup script declares
the two table classes inline on the shared `Base.metadata`, so the tables
are created without editing the shared schema package — exactly as the skill
documents).

## Entity-domain decision — SKIP

Weather stations are neither `stock` nor `country` entities. The daas
`entities` table is typed (`entity_type ∈ {'stock','country'}`) and its
coverage layer (`get_entity_coverage`) is built around ticker/country
identifiers. Per skill Step 4 ("Unrecognized domain (weather, sports, …) →
skip entity registration"), entities + links were left empty:

```
entities count                = 0
entity_datasource_links count = 0
```

The datasource + indicator mapping still landed. A weather-specific entity
type is a future extension, out of scope for this skill.

## DB rows (throwaway `meteostat.db`)

| table | rows | detail |
|---|---|---|
| `canonical_indicators` | 34 | unchanged — seed vocabulary only, NO new indicators minted |
| `column_indicator_mappings` | 0 | none inserted (see matcher result below) |
| `sources` | 1 | `meteostat` (enabled=1) |
| `categories` | 2 | `Weather` (root) → `Weather-Stations` (child) |
| `daas_functions` | 1 | `station_daily` (category=`Weather-Stations`, output_type=`DataFrame`) |
| `daas_function_columns` | 11 | `date, tavg, tmin, tmax, prcp, snow, wdir, wspd, wpgt, pres, tsun` |
| `datasource_forms` | 1 | form_type=`meteostat-default` |
| `datasource_sections` | 1 | `station_daily` (carries the routing instruction) |
| `entities` / `entity_datasource_links` | 0 / 0 | skipped (unrecognized domain) |

## Routing instruction

```
mcp=meteostat-mcp tool=station_daily param=station_id=<ask-agent> param=start=<ask-agent> param=end=<ask-agent>
```

`<ask-agent>` marks the three params the agent must supply (station id + date
range). Grammar regex `^mcp=\S+\s+tool=\S+(\s+param=[^=\s]+=\S+)*$` validated
by the seed script. No `<ask-agent>` is prefilled because there are no
entities → no `identifier_in_source` to plug in.

### `.mcp.json` entry (NOT added — noted only)

The real `.mcp.json` was not modified. The entry that would be added:

```json
"meteostat-mcp": {
  "type": "stdio",
  "command": "uv",
  "args": ["run", "--directory", "/Users/chengsishi/code/cli-anything/mcp/meteostat-mcp", "python", "server.py"]
}
```

## Indicator-mapping result — the core of this eval

```
meteostat: 11 columns — did map 0 (0 confirmed, 0 proposed), 11 unmatched.
```

**0 mapped, 11 unmatched, 0 new canonical indicators minted.**

| column | closest canonical | fuzzy ratio | verdict |
|---|---|---|---|
| date  | debt_to_equity   | 0.667 | unmatched |
| tavg  | pe_ratio         | 0.429 | unmatched |
| tmin  | net_income       | 0.462 | unmatched |
| tmax  | pe_ratio         | 0.444 | unmatched |
| prcp  | open             | 0.615 | unmatched |
| snow  | low              | 0.571 | unmatched |
| wdir  | dividend_yield   | 0.333 | unmatched |
| wspd  | pe_ratio         | 0.333 | unmatched |
| wpgt  | gdp_real_growth_pct | 0.462 | unmatched |
| pres  | pe_ratio         | 0.667 | unmatched |
| tsun  | turnover         | 0.500 | unmatched |

**Why most are unmatched — the skill correctly resisted over-mapping:**

1. **No semantic overlap.** The 34-indicator vocabulary is finance/macro:
   market-data (open/high/low/close/volume/turnover), fundamentals
   (revenue/eps/roe/…), macro (gdp/cpi/unemployment/policy_rate/…),
   alternative (vix/put_call). Weather columns (temperature, precipitation,
   wind, pressure, sunshine) have no canonical financial/macro equivalent.
2. **No cross-source recurrence.** Canonical names earn their place by
   recurring across sources (yfinance.close == akshare.收盘). A weather
   column would be a one-off canonical name for a single source — the skill
   principle explicitly forbids this: *"Do not invent a canonical name for a
   one-off column with no cross-source meaning — leave it unmapped."*
3. **Fuzzy threshold held.** The highest ratio was 0.667 (`date`↔`debt_to_equity`,
   `pres`↔`pe_ratio`) — well below the 0.85 cutoff. No false positives slipped
   through as proposals. The matcher inserts nothing below 0.85, so
   `column_indicator_mappings` stayed empty.
4. **Restraint over force-fitting.** The skill communicated that indicator
   mapping is sparse for this domain rather than minting `temperature`,
   `precipitation`, `wind_speed` etc. just to fill the table. Weather data is
   a genuinely new domain; if a second weather source is ever onboarded
   (e.g. NOAA, Open-Meteo), *then* recurring weather indicators would earn
   canonical names. Until then, one-off columns stay unmapped.

## Verification of the MCP

`uv sync` ran clean. Tools register correctly (verified via in-process
FastMCP `Client.list_tools()`):

```
  tool: station_daily - Fetch daily weather observations for a station over a date range.
  tool: station_info  - Return metadata for a single weather station (name, country, ...)
  tool: find_stations_nearby - Discover weather stations near a lat/lon, closest first.
```

`meteostat` is lazy-imported inside each tool, so the server starts without
the dep installed (mirrors edgartools/edinet). Per-tool errors return a clear
`{error, hint}` when the dep is missing.

## Steps skipped / faked

- **Step 0 models.py paste** — skipped per eval guardrails (the setup script
  declares the two table classes inline on `Base.metadata`, creating the
  tables without editing `mcp/models/models.py`). Throwaway DB bootstrapped
  via `setup_indicator_vocabulary.py` against `DAAS_DATABASE_URL=sqlite:////tmp/fd-dsc-eval/eval3-with/meteostat.db`.
- **Step 2 .mcp.json edit** — NOT performed (eval guardrail). The entry is
  noted above.
- **Step 4 entity registration** — skipped (unrecognized domain), per skill.
- **Step 6 usage skill** — NOT emitted as a separate `.claude/skills/` file
  (would modify the real repo's skills tree). The server's docstring + the
  `station_daily` tool description serve as the usage card; this is noted here
  rather than written to disk to keep the real repo clean per the eval guardrails.
- **No live network call** — per eval instructions, the documented daily-data
  shape (`date, tavg, tmin, tmax, prcp, snow, wdir, wspd, wpgt, pres, tsun`
  from `GET /stations/daily`) was used directly without fetching real weather
  data. The MCP server's `station_daily` tool is wired to call
  `meteostat.daily(...).fetch()` for real use, but no network fetch was
  performed during this eval.
