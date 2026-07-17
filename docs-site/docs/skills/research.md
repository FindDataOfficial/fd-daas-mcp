# fd-daas-research

**Orchestrate a full DAAS research workflow.** This is the flagship skill - it
turns a natural-language demand into a persisted study with indicators, a
dashboard, and a markdown report.

## When it triggers

Phrases like:

- "帮我研究一下比亚迪，做指标和看板"
- "research TSLA - build indicators and a dashboard"
- "研究一下沪深300成分股做个看板"
- "research SSE banks - set up indicators and a dashboard"
- "分析这只股票并做个可视化"

...or any entity + "research / 分析 / 研究 / full pipeline".

## The flow

```
analyze demand -> [entity collection] -> indicators -> dashboard
              -> persist as `research` bundle -> generate markdown report
```

1. **Analyze** the demand into a plan (uses `sqlite3` for plan context).
2. **Build components** via the `fd-daas-*` creator skills:
   - If the demand names a group (watchlist, a rule like "SSE banks", an
     explicit list of codes), it first delegates to
     `fd-daas-entities-collection-creator` to persist the group.
   - Builds indicators over the members.
   - Builds a dashboard.
3. **Persist** the whole study as a `researches` row using the `research_*` MCP
   tools (`research_create`).
4. **Generate a markdown report** (`research_generate_report`) written to
   `researches/<name>.md`.
5. Emits a `skill-run-notification` block.

## Refresh vs. rebuild

On a repeat demand whose research already exists, this skill **refreshes** it
(`research_refresh` - recompute indicators, re-sync rule-based collections) and
regenerates the report instead of rebuilding from scratch. It auto-detects
prior researches.

## What it does NOT do

- Only indicators? Use `fd-daas-indicators-creator`.
- Only a dashboard? Use `fd-daas-dashboard-creator`.
- A one-shot fetch? Use `fd-daas-fetch-data`.
- Only an entity collection? Use `fd-daas-entities-collection-creator`.

This skill orchestrates the **full** analyze -> [collection] -> indicators ->
dashboard -> research-bundle flow.

## Example

> Research BYD's trend: build the entity + indicator collections, compute the
> indicators, make a dashboard, and persist it as a research bundle with a
> markdown report.

Result:

```text
researches/byd-trend.md          # generated report
researches row in daas.db        # persisted bundle
dashboards/<slug>/index.html     # dashboard
```

## MCP equivalents

```text
research_create(name="byd-trend", entity_collection_name=..., indicator_collection_name=..., dashboard_slug=..., pipeline_collection_name=...)
research_generate_report(name="byd-trend")
research_refresh(name="byd-trend")        # later, to refresh data
research_get(name="byd-trend")            # inspect
```

## Works for any scope

Company, industry (a collection of stocks), city, or country - the collections
you build define the scope. See [Create a Research](../examples/create-research.md).
