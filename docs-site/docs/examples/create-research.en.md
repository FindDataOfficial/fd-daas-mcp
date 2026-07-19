# Create a Research

A **research** is DAAS's top-level artifact: a persisted bundle that ties an
entity collection, an indicator collection, a dashboard, and a data pipeline to
a generated markdown report. Use it for a company, an industry, a city, or a
country.

## The flow

```
goal -> brainstorm (optional) -> [entity collection] + [indicator collection]
     -> indicators computed -> dashboard -> research bundle -> markdown report
```

## 1. (Optional) Brainstorm the goal

If your goal is fuzzy, start with `fd-daas-brainstorm`. It clarifies the goal
through dialogue and writes a plan to `daas-doc/research/<plan-slug>.md` - no
`daas.db` state. See [fd-daas-brainstorm](../skills/brainstorm.md).

## 2. Run the research skill

The `fd-daas-research` skill orchestrates the whole flow. In Claude Code:

> Run a research on BYD's trend: build the entity + indicator collections,
> compute the indicators, make a dashboard, and persist it as a research bundle
> with a markdown report.

The skill:

1. Auto-detects prior researches and decides refresh-vs-rebuild.
2. Builds (or reuses) the entity + indicator collections.
3. Computes each indicator (`daas_run_indicator`) and syncs rule-based
   collections.
4. Creates/updates a dashboard.
5. Persists a `researches` row + writes `researches/<name>.md`.
6. Emits a `skill-run-notification` block.

## 3. Run via MCP

If you prefer direct tool calls:

```text
research_create(name="byd-trend",
                entity_collection_name="byd-watchlist",
                indicator_collection_name="byd-momentum",
                dashboard_slug="byd-trend",
                pipeline_collection_name="byd-pipeline")
research_generate_report(name="byd-trend")
```

**Refresh** the data later (recompute indicators, re-sync collections):

```text
research_refresh(name="byd-trend")
```

## 4. Inspect

```bash
sqlite3 daas.db "SELECT name, status, report_path FROM researches;"
cat researches/byd-trend.md
```

Or via MCP: `research_get(name="byd-trend")` / `research_list()`.

## Works for any entity type

The same flow works for a **company** (BYD, AAPL), an **industry** (a collection
of stocks), a **city** (a regional entity + its indicators), or a **country**
(CN/US macro series). The collections you build define the scope.

## Next

- See the dashboard you just made: [Share a Dashboard](share-dashboard.md).
- Understand the bundle: [fd-daas-research](../skills/research.md).
