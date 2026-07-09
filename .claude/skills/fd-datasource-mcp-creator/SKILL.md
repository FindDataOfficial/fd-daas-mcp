---
name: fd-datasource-mcp-creator
description: |
  Onboard any Python package, library, or GitHub project as a first-class daas
  datasource in mcp/daas.db. Analyzes the package's data surface, builds a
  working MCP server for it, registers the datasource (sources + functions +
  columns + a routing form/section), registers the entities it covers +
  entity↔datasource links, and auto-maps its output columns to a canonical
  indicator vocabulary stored in mcp/daas.db. Use this skill whenever the user
  wants to wrap a library/package/repo as a data source — phrases like "build
  an mcp for this package", "add X as a datasource", "turn this github repo
  into an mcp", "register a new datasource from this library", "what
  indicators does this package provide", or any "package/repo/library" +
  "mcp/datasource/data source" combination. Also use when the user wants to
  map datasource columns to canonical indicator names, extend the canonical
  indicator vocabulary, or figure out which indicators a new source exposes.
  Prefer this skill over fd-daas-mcp-builder when the input is an arbitrary
  package/repo (not an existing DAAS adapter) or when entity + indicator
  mapping is wanted alongside the MCP.
---

# fd-datasource-mcp-creator

Onboard any Python package or GitHub project as a first-class daas datasource —
one end-to-end pass that produces the MCP server, the daas registration, the
entity links, and a column→indicator mapping, all in `mcp/daas.db`.

## What this skill produces

For a given package/repo, in one pass:

1. **An MCP server** at `mcp/<source>-mcp/` wrapping the package's data surface.
2. **A daas datasource** registered in `mcp/daas.db`: a `sources` row +
   `daas_functions` + `daas_function_columns` + a routing `datasource_forms`/
   `datasource_sections` (so an agent can dispatch deterministically).
3. **Entities + links** — the entities the source covers (stocks, countries, …)
   and `entity_datasource_links` with a resolved `identifier_in_source`.
4. **A column→indicator mapping** — each output column matched to a canonical
   indicator name in the new `canonical_indicators` vocabulary, recorded in
   `column_indicator_mappings` with a match method + confidence.
5. **A usage skill** at `.claude/skills/<source>-usage/` so other agents can
   drive the new MCP.

## Mental model — the daas layer (condensed)

Everything lives in the single shared `mcp/daas.db`. The full reference is
`references/daas-concepts.md` (condensed from `construction/daas-storage.md`);
read it once before your first run. The five concepts this skill touches:

| concept | table(s) | role |
|---|---|---|
| **datasource** | `sources` | a managed data source (akshare, edgar, your new one). Referenced **by name as a soft string** everywhere. |
| **function catalog** | `daas_functions` + `daas_function_columns` | what the source can return + the columns each function outputs. This is what the matcher maps. |
| **routing** | `datasource_forms` + `datasource_sections` | a tiny grammar `mcp=<mcp> tool=<tool> param=k=v` so an agent can call the source with zero extra lookups. |
| **entities** | `entities` + `entity_datasource_links` | the real-world things a source describes (a stock, a country), linked to `sources` with a ready-to-use `identifier_in_source`. |
| **indicator vocabulary** *(new)* | `canonical_indicators` + `column_indicator_mappings` | a curated set of canonical indicator names (`close`, `market_cap`, `gdp_nominal_usd`, …) that columns map **to**, so the same indicator is queryable uniformly across sources. |

**The new tables** (added once by Step 0, additive — no Alembic):

```
canonical_indicators
  name          VARCHAR(64) UNIQUE   -- 'close', 'market_cap', 'gdp_nominal_usd'
  label         VARCHAR(128)          -- 'Closing price'
  unit          VARCHAR(32)           -- 'USD', '%', 'ratio', 'count'
  semantic_type VARCHAR(32)          -- 'price','volume','ratio','index','rate'
  category      VARCHAR(64)          -- 'market-data','fundamentals','macro','alternative'
  aliases       JSON                  -- ["收盘","收盘价","Close*","Last"]
  description   TEXT

column_indicator_mappings
  source         VARCHAR(64)   -- soft ref to sources.name
  function_name  VARCHAR(255)
  column_name    VARCHAR(255)
  indicator_name VARCHAR(64)    -- soft ref to canonical_indicators.name
  match_method   VARCHAR(16)   -- 'exact' | 'alias' | 'fuzzy' | 'manual'
  confidence     FLOAT          -- 0.0–1.0
  confirmed      BOOLEAN        -- 0 = proposed, 1 = human-confirmed
  UNIQUE (source, function_name, column_name)
```

Soft string refs everywhere (mirrors `observations.source` / `indicator_rules.datasource`) —
a source can be renamed/recreated without breaking mappings. No FK across to
`daas_function_columns` (avoids the cross-table FK gotcha in daas-storage §4).

## When to delegate vs build

- **Input is a CLI-Anything harness** (`cli_anything/<name>/`) **or has a
  `registry.json` / a `*_source.py` DAAS adapter** → invoke the
  `fd-daas-mcp-builder` skill. It generates the registry-style MCP (5 tools:
  search/detail/list/categories/call) and populates `daas.db` from the adapter.
  Then continue this skill at **Step 3** (register routing form/section +
  entities + indicator mapping — the builder skips those).
- **Otherwise** (arbitrary package/repo with a Python API, no flat function
  catalog) → build a **purpose-built** MCP from
  `references/purpose-built-server-template.py` (edgartools-style: FastMCP +
  hand-written tools wrapping the package's object/functional API). Then do
  all steps 1→6.

The two MCP styles already coexist in the repo: `akshare`/`yfinance` are
registry-style; `edgartools`/`cnreport`/`hkreport` are purpose-built. Match the
style to the input — don't force a flat function catalog onto an object API.

## Workflow

### Step 0 — Ensure the indicator vocabulary exists (once per repo)

Idempotent. Run before the first source onboarding; skip on later runs (the
tables + seed already exist).

1. **Add the two model classes** to `mcp/models/models.py` (the shared schema
   package — schema changes go here first, per project convention). Use the
   class definitions in `references/daas-concepts.md` §"Model classes". They
   use `Base.metadata.create_all` (additive, no Alembic, mirrors every other
   daas table).
2. **Create + seed**:
   ```bash
   uv run --directory mcp/daas-mcp python ../../.claude/skills/fd-datasource-mcp-creator/scripts/setup_indicator_vocabulary.py
   ```
   The script parses `references/canonical-indicators.md` (the human-readable
   source of truth) and upserts each row into `canonical_indicators`.
   Re-runnable; `--unseed` drops the two tables for a clean rollback.

Confirm before moving on: `sqlite3 mcp/daas.db "SELECT COUNT(*) FROM canonical_indicators;"`
should be ≥ the seed size (~30).

### Step 1 — Analyze the package

Read the README / `pyproject.toml` / docs. Import the package (or read its
public symbols) and identify:

- **Data surface** — the classes/functions/endpoints that return data (e.g.
  `yfinance.Ticker(sym).history(...)`, `edgar.Company(cik).get_filings(...)`).
- **Output columns / fields** for each — from docs, type hints, or one sample
  call. These become `daas_function_columns` (and the matcher's input).
- **Entity domain** — stocks? macro? crypto? none? Drives Step 4.
- **Auth** — API key? descriptive User-Agent? OAuth? Note which env vars.
- **Dependency** — the pip/uv package name + any `requires-python` floor.

Write a short analysis to `daas-doc/<source>/analysis.md` and show it to the
user before generating code. If the package's data surface is unclear, ask the
user for 1–2 example calls — that's the fastest way to nail the columns.

### Step 2 — Build the MCP

**Delegate** (harness/adapter exists) → invoke `fd-daas-mcp-builder`; it
writes `mcp/<source>-mcp/`, runs `uv sync`, and registers in `.mcp.json`.

**Build purpose-built** → from `references/purpose-built-server-template.py`:

1. Write `mcp/<source>-mcp/server.py` (FastMCP, lazy-import the package so the
   server starts without the dep, `_serialize()` helper, clear per-tool errors
   when the dep/auth is missing).
2. Write `mcp/<source>-mcp/pyproject.toml` (uv-managed; declare the dep +
   `python-dotenv` + `fastmcp`; set `requires-python` if the package has a
   floor).
3. Write `mcp/<source>-mcp/.env.example` (the source's env vars + comments).
4. `cd mcp/<source>-mcp && uv sync`.
5. Register in `.mcp.json`:
   ```json
   "<source>-mcp": {
     "type": "stdio",
     "command": "uv",
     "args": ["run", "--directory", "/Users/chengsishi/code/cli-anything/mcp/<source>-mcp", "python", "server.py"]
   }
   ```
6. Verify tools register: `uv run --directory mcp/<source>-mcp python -c "import asyncio; from server import app; ..."`

### Step 3 — Register the datasource in daas.db

Use **daas-mcp tools** (not hand-rolled SQL) so the write path matches the
dashboard's:

1. `create_category(name=<child>, parent_name=<parent>)` under an appropriate
   parent (`Market-Data` / `Macro` / `Filings` / a new root for the domain).
2. `create_datasource(name=<source>, label, description, url, category)`.
3. Register **functions + columns**: for registry-style sources the builder
   already populated `daas_functions`/`daas_function_columns` from the adapter —
   skip. For purpose-built sources, register the "logical functions" from the
   Step-1 analysis even though the live API is object-shaped — these rows are
   what the matcher reads. Use `daas-mcp`'s column-registration path (mirror
   `references/datasource-seed-template.py`, or the `create_datasource` /
   column tools). Note: `daas_function_columns` has no `semantic_type` column
   (only the dashboard's `datasource_columns` does), so don't try to set one —
   the matcher matches by name/alias/fuzzy only.
4. `add_form` + `add_section` with the routing grammar, one section per
   logical function:
   ```
   mcp=<source>-mcp tool=<tool> param=<key>=<ask-agent> param=<key>=<value>
   ```
   Use `<ask-agent>` for params the agent must supply (ticker, date);
   pre-fill known ones. Validate with the grammar regex in
   `references/datasource-seed-template.py`.

### Step 4 — Register entities + links

Only when the domain maps to a known entity type. Reuse `entity_sync.py`'s
rules where they fit; otherwise link manually.

- **Stocks** → for each ticker the source covers, `link_entity_datasource(
  entity_code/ticker, source_name=<source>,
  identifier_in_source=<form the source expects>)`. e.g. yfinance wants
  `600519.SS`; edgar accepts a ticker; cnreport wants `600519`.
- **Macro / countries** → link `country` entities to the source.
- **Unrecognized domain** (weather, sports, …) → skip entity registration,
  note it in `daas-doc/<source>/analysis.md`, and move on. The datasource +
  indicator mapping still land.

If a bulk entity import is needed and the source has a "list all tickers /
list all countries" call, write a one-off seed script mirroring
`mcp/daas-mcp/entity_sync.py` (lazy-import, per-record failure isolation,
idempotent upsert on `(entity_type, code)`).

### Step 5 — Map columns to canonical indicators

```bash
uv run --directory mcp/daas-mcp python ../../.claude/skills/fd-datasource-mcp-creator/scripts/match_columns_to_indicators.py --source <source>
```

The matcher reads `daas_function_columns` for `<source>`, matches each column
against `canonical_indicators` by:

1. **exact** — column name (lowercased, alnum-only) == canonical name → conf 1.0
2. **alias** — column matches a canonical alias → conf 0.95
3. **fuzzy** — `difflib` ratio ≥ 0.85 vs names+aliases → conf = ratio

`exact` + `alias` auto-confirm (`confirmed=1`); `fuzzy` lands as a **proposal**
(`confirmed=0`) for the user to review. Unmatched columns are left unmapped (not
inserted) and listed.

After it runs, **show the user the proposals** (the low-confidence rows) and
offer to confirm/edit. To extend the vocabulary for a column that should map
but has no canonical name yet: add a row to
`references/canonical-indicators.md`, re-run `setup_indicator_vocabulary.py`,
then re-run the matcher.

### Step 6 — Emit a usage skill

Create `.claude/skills/<source>-usage/SKILL.md` documenting the new MCP:
the tools it exposes, the auth env vars, and 2–3 example calls (one search,
one fetch, one indicator). This is the skill other agents (or a human) consult
to drive the new MCP. Keep it short — it's a usage card, not a tutorial.

## Extending the canonical vocabulary

The vocabulary is intentionally seed-sized (~30 indicators across market-data,
fundamentals, macro, alternative). It is **not** closed — when a new source
introduces a column that deserves its own canonical name (e.g. `vix_close`,
`put_call_ratio`), add it:

1. Add a row to `references/canonical-indicators.md` (name, label, unit,
   semantic_type, category, aliases, description).
2. Re-run `setup_indicator_vocabulary.py` (upserts the new row).
3. Re-run the matcher for the relevant source(s).

Do **not** invent a canonical name for a one-off column with no cross-source
meaning — leave it unmapped. Canonical names earn their place by recurring
across sources.

## Reference files

- **`references/daas-concepts.md`** — entities, datasources, functions/columns,
  routing, indicators (condensed from `construction/daas-storage.md`). Read on
  first run. Includes the model-class source for the two new tables.
- **`references/canonical-indicators.md`** — the seed canonical vocabulary.
  Source of truth; the setup script parses it. Extend here when adding names.
- **`references/purpose-built-server-template.py`** — edgartools-style FastMCP
  template (lazy import, `_serialize`, per-tool auth guards).
- **`references/datasource-seed-template.py`** — the form/section/routing-grammar
  pattern + grammar regex (mirrors `mcp/daas-mcp/seed_external_mcps.py`).
- **`scripts/setup_indicator_vocabulary.py`** — idempotent table-create + seed.
- **`scripts/match_columns_to_indicators.py`** — the auto-matcher.

## Principles

- **One source of truth.** `mcp/daas.db` holds the datasource, columns, entities,
  and indicator mappings. The `.md` references are human-readable mirrors; the DB
  is authoritative for everything except the canonical-vocab seed list (where the
  `.md` is authoritative and the DB is seeded from it).
- **Soft string refs across concepts.** `column_indicator_mappings.source` and
  `.indicator_name` are plain strings — renames don't break history. Real FKs
  only within a cohesive unit (collection→item), mirroring the rest of daas.
- **Additive schema.** New tables via `Base.metadata.create_all`, no Alembic,
  guarded `ALTER TABLE` for any added column on an existing table.
- **Routing grammar, not free text.** `mcp=… tool=… param=k=v` so an agent can
  dispatch deterministically — same convention as `seed_external_mcps.py`.
- **Auto-match is a draft.** Low-confidence matches stay `confirmed=0` for human
  review; never silently auto-confirm a fuzzy guess.
- **Match style to input.** Don't force a registry onto an object API. Detect &
  delegate when an adapter exists; purpose-build otherwise.
