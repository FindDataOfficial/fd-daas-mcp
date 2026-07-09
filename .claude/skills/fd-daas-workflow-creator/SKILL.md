---
name: fd-daas-workflow-creator
description: Summarize a completed multi-step daas flow and persist it as a resumable leader-mcp workflow — prefer build_workflow_from_goal (LLM decomposition), fall back to manual create_workflow + add_workflow_step when no LLM is configured. Use this skill whenever the user wants to save a just-executed flow as a replayable workflow — phrases like "把刚才这套流程存成一个 workflow", "save this flow as a workflow", "把这个数据流程固化下来", "create a workflow from what we just did", or any completed daas flow + "workflow / 固化 / 存成流程". Do NOT use this skill to RUN a workflow (use mcp__leader-mcp__run_workflow directly) or to create indicators/dashboards (use the fd-daas-* creator skills); this skill only summarizes + persists the flow as a workflow, then writes a `daas-doc/<workflow-name>/plan.md` doc and passes the workflow-name to nested child skills.
---

# fd-daas-workflow-creator

Summarize a completed flow → persist it as a leader-mcp workflow. Default model tier is `fast` (data-fetch pipelines aren't reasoning-heavy); user can override to `balance` / `high`.

## Mental model

Four steps:

1. **Summarize the flow** → ordered step list (upstream MCP + tool + arguments per step). Get user confirmation.
2. **Persist** — prefer `mcp__leader-mcp__build_workflow_from_goal` (default `model="fast"`). When no LLM is configured (deterministic single-step fallback), fall back to manual `create_workflow` + `add_workflow_step` per step. **The fallback is NOT an error.**
3. **Write plan.md** — derive a kebab-case `<workflow-name>` from the goal, write `daas-doc/<workflow-name>/plan.md` (goal, step list, tier, workflow name). Pass `workflow-name <X>` to any nested child creator skill.
4. **Optionally run** — offer `run_workflow` (all steps) or `run_workflow_step` (one step). No auto-run without consent.

## Step 1 — Summarize the flow

Goal: turn the just-executed flow into an ordered, reviewable step list.

1. Read the recent conversation / executed steps. For each step, capture: the upstream MCP (`source_mcp`, e.g. `akshare-mcp`), the tool (e.g. `call_akshare_function`), and the `arguments_json` (e.g. `{"name":"stock_zh_a_hist","params_json":"…"}`).
2. Order the steps by execution order. If a step depends on a prior step's output (e.g. an indicator over a freshly-backfilled `scraw_<slug>`), mark the `depends_on`.
3. Show the summary to the user as a numbered list and ask: "Does this capture the flow? I'll persist it as a workflow."

**Empty flow**: if there's no recent flow to summarize (e.g. the user invokes this skill cold), tell the user "no recent flow to capture — run a flow first (e.g. via `fd-daas-indicators-creator`) then re-invoke" and STOP.

## Step 2 — Persist via build_workflow_from_goal (preferred, default fast)

1. Compose a `goal` string from the summary (e.g. "Fetch 比亚迪 daily OHLCV via akshare, compute a 5-day SMA, persist to scraw_byd_daily_sma5, refresh on a weekday cron").
2. Call `mcp__leader-mcp__build_workflow_from_goal(goal, name="<kebab-name>", description="...", model="fast")`.
   - **Default tier is `fast`** — data-fetch pipelines aren't reasoning-heavy. Accept an optional override from the user (`balance` / `high`) for harder decompositions.
   - The builder decomposes the goal into specialist-agent steps and persists them via `create_workflow` + `add_workflow_step`. It returns the created workflow + a `warnings` list.
3. Confirm to the user: "Workflow `<name>` created with N steps (tier=fast)."

**User picks a non-default tier**: if the user asks for `high` or `balance`, call `build_workflow_from_goal` with that tier instead.

## Step 3 — Fall back to manual construction (no LLM)

When `build_workflow_from_goal` returns a deterministic **single-step** workflow (the marker that `crewai` is unavailable or no LLM is configured), do NOT treat it as an error. Instead:

1. Tell the user: "The leader-mcp LLM is unavailable, so `build_workflow_from_goal` fell back to a single-step workflow. I'll construct the workflow manually from the summarized steps instead."
2. Call `mcp__leader-mcp__create_workflow(name="<kebab-name>", description="...")` once.
3. For each summarized step, call `mcp__leader-mcp__add_workflow_step(workflow_name="<name>", agent="<specialist-agent>", request="<what this step does>", depends_on="<prior step sort_orders>")`. Pick the `agent` from `mcp__leader-mcp__list_specialist_agents` (one per upstream — e.g. `akshare-agent` for an akshare fetch step).
4. Confirm to the user: "Workflow `<name>` created with N manual steps (no-LLM fallback)."

The fallback path is recorded in each step's `meta` by leader-mcp, so the workflow runs end-to-end without an LLM.

## Step 4 — Write plan.md + hand off nesting

Goal: leave a human-readable plan + enable child skills to co-locate their docs.

1. **Derive `<workflow-name>`** — slugify the composed goal (kebab-case, truncate ~40 chars). If the goal is empty or `daas-doc/<workflow-name>/` already exists, fall back to `workflow-<YYYYMMDD>-<HHMMSS>` (computed in-skill — the skill layer is not subject to the `Workflow` JS sandbox's `Date.now` restriction). Create `daas-doc/<workflow-name>/`.
2. **Write `daas-doc/<workflow-name>/plan.md`** — capture: the workflow-name, the composed goal, the persisted leader-mcp workflow name, the step list (upstream MCP, tool, arguments per step), the chosen tier, and the created date. Plain markdown, no JS.
3. **Hand off to nested children** — if this skill delegates to a child creator (`fd-daas-dashboard-creator`, `fd-daas-indicators-collection-creator`) via the `Skill` tool, include a `workflow-name <X>` token in the child's `args` so the child writes its doc under `daas-doc/<X>/` instead of its standalone default.

Writing `plan.md` is additional to (not a replacement for) persisting the workflow in leader-mcp — the persist path (steps 2–3) is unchanged. Report the `plan.md` path to the user. See `construction/daas-doc.md` for the shared layout.

## Step 5 — Optionally run

After persisting, offer to run:

- **All steps**: `mcp__leader-mcp__run_workflow(name="<name>")` → returns run id + per-step results.
- **One step at a time**: `mcp__leader-mcp__run_workflow_step(name="<name>", step_sort_order=<N>)` → resumes an `in_progress` run or starts a new one.

Do NOT auto-run without user consent. If the user declines, report the workflow name + step count and stop.

## Gotchas

- **Default tier is `fast`.** `build_workflow_from_goal(goal, name, description, model="fast")`. Override to `balance` / `high` only when the user asks or the decomposition is genuinely hard.
- **The no-LLM fallback is not an error.** `build_workflow_from_goal` returns a single-step workflow when `crewai` is unavailable or no LLM is configured — detect it (single step, or a `warnings` entry mentioning the fallback) and switch to manual `create_workflow` + `add_workflow_step`.
- **`depends_on`** is a comma-separated list of prior step `sort_order`s whose raw output is injected as text context into the current step. Use it when a step consumes a prior step's output.
- **Step `output_json` is capped at 1 MB** by leader-mcp. If a fetch step returns more, the excess is truncated — design steps to return summaries, not raw dumps.
- **Specialist agents are one per upstream** (e.g. `akshare-agent`, `yfinance-agent`). Pick the agent whose `upstream` matches the step's `source_mcp`. `list_specialist_agents` shows them.
- This skill only summarizes + persists. To RUN a workflow later, use `run_workflow` directly — no need to re-invoke this skill.
- **`daas-doc/<workflow-name>/plan.md` is always written.** The workflow-name is a kebab slug of the goal (timestamp fallback on collision). Pass `workflow-name <X>` in a child skill's `args` when you want its doc nested under the same folder — the token is the only nesting signal (no env var, no sentinel file). See `construction/daas-doc.md`.
