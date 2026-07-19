# daas-mcp concepts (for creating/reviewing daas skills)

This is the shared domain knowledge every `fd-daas-*` skill must be consistent
with. Inject these as guardrails when creating a new daas skill, and check them
when reviewing one. Source of truth: repo-root `CLAUDE.md` + `daas.db`.

## 1. Architecture: skill + sqlite

Data fetch is **skill-driven**: skills call Python data libraries
(`akshare`, `yfinance`, `edgar`, `edinet-tools`, `dartlab`, `world_bank_data`,
`ckanapi`) directly and read/write `daas.db` via `sqlite3`. The consolidated
**`fd-daas-mcp`** MCP server is the sole entry in repo-root `.mcp.json` - it
hosts the `alerts`/`cron`/`composite`/`daas`/`dashboard`/`leader`/`pdf`/
`research` tool groups (187 tools; `pdf` optional, gated on `sqlite-vec`)
behind one stdio server and one `fd-daas-mcp` Click CLI. The thin consolidation
layer is `fd-daas-mcp/daas/fd_daas_mcp/` (`server.py`/`registry.py`/`cli.py`/
`selfcheck.py`); each group's tool code lives in-package at
`fd-daas-mcp/<group>-mcp/`.

## 2. daas.db

SQLite at the path in `DAAS_DATABASE_URL` (relative `sqlite:///` paths resolve
against the repo root; canonical DB is the git-tracked repo-root `daas.db`).
Query from repo root: `sqlite3 daas.db "SELECT ..."`; `PRAGMA foreign_keys=ON`.

Key tables:
- `sources`, `daas_functions`, `daas_function_columns` - datasource/function/column catalog.
- `entities`, `entity_datasource_links` - stocks/countries + source identifiers.
- `indicator_rules` - indicator bindings (name, datasource, source_table, date_column, value_column, op, params_json, indicator_name, enabled, score).
- `observations` - computed indicator series, keyed on `(source, function_name, indicator, date)`, `value` VARCHAR(64).
- `dashboards` - standalone-HTML dashboard registry.
- `scraw_<slug>` - scraped/fetched source-data tables (auto-created by `upsert.py`).
- `entity_collections`, `entity_collection_items`, `entity_collection_changes` - named entity groups + audit.
- `indicator_collections`, `indicator_collection_items`, `indicator_collection_changes` - named indicator groups + audit.
- `rules` - unified rule store (`rule_type` ∈ json/script/position/llm; `target` ∈ entity_ids/indicator_names/rows).
- `pdf_documents`/`pdf_meta`/`pdf_chunks` (+ `pdf_chunks_vec` `vec0`) - local vector search.
- `researches` - persisted research bundle.

## 3. Dispatch prefixes (skill-driven fetch)

The replacement layer lives in `.claude/skills/fd-daas-based-data-fetch/`. Map
each source prefix to its Python lib + call shape via
`scripts/dispatch.py --resolve <func>`:

| Prefix | Library |
| --- | --- |
| `akshare_` | akshare |
| `yfinance_` | yfinance |
| `edgar_` | edgar |
| `edinet_` | edinet-tools |
| `dartlab_` | dartlab (Python 3.12) |
| `worldbank_` / `wbdata_` | world_bank_data |
| `cnstats_` | cnstats |
| `ckan_` | ckanapi |

Shared scripts: `scripts/db.py` (sqlite3 helper, reads `DAAS_DATABASE_URL`),
`scripts/run_indicator.py` (deterministic indicators: sma/ema/rsi/pct_change/
log_return/diff/rolling_std/rolling_min/rolling_max/zscore/ratio/level;
`--list-ops`), `scripts/upsert.py` (persist to `scraw_<slug>` or `observations`,
backs up `daas.db` first).

## 4. Environment

Use **uv**. Python 3.10+ (dartlab needs 3.12: `uv run --python 3.12 --with dartlab ...`).
Single `.env` at repo root: `DAAS_DATABASE_URL` (`sqlite:///daas.db`),
`HTTP_PROXY`, `EDGAR_IDENTITY`, `EDINET_API_KEY`, `LLM_*`/`LEADER_MODEL*`,
`ALERTS_FEISHU_WEBHOOK_URL`, `DASHBOARD_PORT`, `CKAN_PORTAL_URL`. Scripts load
`.env` automatically.

## 5. daas-doc/ path conventions

Skill-generated human-readable markdown docs live under repo-root `daas-doc/`
(not the Next.js `dashboard/` app). Create `daas-doc/` and subdirs on first use.
Standalone paths:
- `fd-daas-dashboard-creator`: `daas-doc/dashboard/<custom-name>-dashboard.md`
- `fd-daas-indicators-collection-creator`: `daas-doc/indicators/<collection>.md`
- `fd-daas-brainstorm`: `daas-doc/research/<plan-slug>.md`
- MCP test-suite doc: `daas-doc/mcp-test-suite.md`
- Skills test report: `daas-doc/skills-test-report/<timestamp>-report.md`

(`fd-daas-workflow-creator` was removed - do not reference its nesting paths.)

## 6. skill-run-notification convention

Daas skills that run a workflow SHALL emit a fixed-format block at the end of
every run (see the `skill-run-notification` spec). Heading is one of
`## Run Complete` / `## Run Paused` / `## Run Failed`, with fields
`**Skill:**`, `**Status:**`, `**Produced:**`, `**Next:**`. Example:

```
## Run Complete

**Skill:** fd-daas-research
**Status:** created + reported
**Produced:** research `byd-trend` -> `researches/byd-trend.md`; dashboard http://...
**Next:** re-run anytime to refresh (`research_refresh`); ask me to tweak indicators.
```

## 7. Defect vocabulary (fd-daas-skills-test-suite)

When inspecting/reviewing, tag every defect with exactly one class:
- `script-bug` - helper script missing / wrong-path / import-error / crash.
- `stale-ref` - reference to a removed CLI / MCP group / `mcp__*` tool / old DB URL / deleted file.
- `routing-drift` - trigger description routes to the wrong skill, or two skills collide on the same trigger.
- `malformed` - missing `SKILL.md`, bad frontmatter, broken markdown, dead internal links.

## 8. Removed surfaces - DO NOT reference

Removed CLIs: `fd-akshare`/`fd-yfinance`/`fd-dartlab`/`fd-edgar`/`fd-edinet`/`fd-world`.
Removed skills/groups: `fd-daas-workflow-creator`, `fd-daas-scraw-scrapling`,
`fd-daas-scrapling-scraw-creator`, `fd-daas-cli-datasource-entities-builder`,
per-source `mcp__*` tools, and the `scrapling`/`firecrawl`/`massive` MCP groups.
The `cron`/`alerts`/`leader`/`composite` MCPs are **not** removed - they are
folded into `fd-daas-mcp` as `<group>_<tool>`. `pdf` was restored (optional).

## 9. fd-daas-* skill family (routing boundaries)

- `fd-daas-based-data-fetch` - core resolve->fetch->persist.
- `fd-daas-fetch-data` - entity->coverage->indicator workflow.
- `fd-datasource-akshare` - A-share OHLCV/fundamentals via the external `scraw-akshare` Scrapy project.
- `fd-daas-indicators-creator` - persist a series to `scraw_<slug>` (no cron).
- `fd-daas-dashboard` / `fd-daas-dashboard-creator` - browse/build HTML dashboards.
- `fd-daas-research` - orchestrate analyze->[collection]->indicators->dashboard->persist as a `research` bundle + report.
- `fd-daas-entities-collection` / `-creator` - entity collections + rules.
- `fd-daas-indicators-collection-creator` - indicator collections + export.
- `fd-daas-rules-creator` - author a unified rule, attach, dry-run, sync.
- `fd-daas-pdf` - local PDF/text semantic vector search.
- `fd-daas-scrapling-official` - web scraping with anti-bot bypass (the Scrapling library, not the dropped MCP group).
- `fd-daas-brainstorm` - clarify a research goal -> plan doc (no daas.db state).
- `fd-daas-skill-creator` / `fd-daas-skill-review` - create/review daas skills (this skill family's meta-skills).

When creating a new skill, give it a `description` that triggers on its intent
without colliding with the above (avoid `routing-drift`).
