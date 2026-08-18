---
name: fd-daas-research
description: Run a daas research study by executing the registered `research` workflow manifest, which searches concepts via fd-open-data-mcp, persists a research bundle, and generates a markdown report. Use when the user wants a full research pipeline (entity -> indicators -> dashboard -> report). Returns the research handle + report path. No direct component delegation, no direct sqlite3 plan context.
---

# fd-daas-research (thin shell)

Run a research study by running the `research` workflow manifest. The manifest
owns concept search -> `research_create` -> `research_generate_report` over
fd-open-data-mcp + fd-daas-mcp; this skill gathers params, runs the manifest,
handles checkpoints, and surfaces the report. No delegated creator-skill
invocation, no direct `sqlite3` plan context, no direct `research_*` MCP calls
— those moved behind the manifest.

## When to use

- "研究一下比亚迪，做指标和看板 / research TSLA - build indicators and a dashboard"
- "research SSE banks - set up indicators and a dashboard"
- "分析这只股票并做个可视化"

Do NOT use for: a one-shot fetch (`fd-daas-based-data-fetch`), only indicators
(`fd-daas-indicators-creator`), only a dashboard (`fd-daas-dashboard-creator`),
or only an entity collection (`fd-daas-entities-collection-creator`).

## Step 1 — Gather params

The `research` manifest takes:

| param | type | how to discover |
|-------|------|-----------------|
| `name` | str (kebab/snake handle) | derive from entity/group + lens |
| `query` | str (natural-language demand) | user demand verbatim |
| `limit` | int | default 10; raise for broader concept search |

## Step 2 — Run the manifest

```python
workflow_run(name="research", params_json=json.dumps({
    "name": "byd-trend",
    "query": "比亚迪 趋势 价格 指标",
    "limit": 10
}))
```

Returns `outputs`: `{"concepts": [...], "research": {...}, "report": {...}}`.
`concepts` is the ai_search result list; `research` is the created bundle row;
`report` carries the `report_path` (`researches/<name>.md`).

## Step 3 — Checkpoint handling

If `status` is `paused`, the manifest hit a `type: checkpoint` step. Inspect
the `resume_token` + the sentinel step at `sort_order=0`, decide, then:

```python
workflow_resume(run_id=<run_id>, approved=True)   # approved=False marks the run failed
```

`workflow_inspect(name="research")` shows the validated step plan without
executing — use it to preview before a run.

## Step 4 — Surface the result

Tell the user the research name + the returned `report_path`. On a repeat
demand whose research already exists, re-run Step 2 — `research_create`
upserts the bundle and `research_generate_report` regenerates the markdown.

For a full indicator recompute (re-run the indicator math + sync rule-based
collections), call `research_refresh(name="<name>")` as a follow-up; the
manifest itself only creates + reports, it does not invoke refresh.

**Run-notification** — emit at the end:

    ## Run Complete
    **Skill:** fd-daas-research
    **Status:** research manifest run + reported
    **Produced:** research `<name>` -> `researches/<name>.md`
    **Next:** re-run anytime to refresh; `research_refresh` to recompute indicators.

## Hard rules

- **Orchestration goes through `workflow_run("research", …)`.** No direct
  `research_*` MCP calls, no delegated creator-skill invocation, no direct
  `sqlite3` plan context. The manifest owns search -> create -> report; this
  skill owns param gathering + result surfacing.
- **No standalone fetch step** — wiring concept_id generically out of
  ai_search's list result needs list-index interpolation the manifest engine
  doesn't support; fetch is folded into `research_refresh` (run separately on
  repeat demands to recompute indicators), not the manifest.
- **No cron by default.** Re-run Step 2 to refresh the report.
