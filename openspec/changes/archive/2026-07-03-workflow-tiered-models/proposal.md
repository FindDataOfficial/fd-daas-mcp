## Why

`leader-mcp`'s crewai-data-workflow layer currently has no model-tier concept: every specialist agent and workflow step either pins one concrete `LEADER_MODELS` entry or falls back to the shared `LLM_MODEL`. That forces a single model choice onto two very different workloads — cheap, high-volume data fetching (where a fast/cheap model is plenty) and complex reasoning (workflow planning, synthesis, where a strong model pays off). There is also no way to generate a workflow from a goal; workflows are assembled by hand. This change introduces a `high` / `balance` / `fast` tier abstraction over `LEADER_MODELS`, defaults data-fetch steps to `fast`, and adds an LLM-driven workflow builder that defaults to `high` — so cost and quality line up with the task.

## What Changes

- Add `deepseek-v4-flash` and `glm-5.2` as named entries in `LEADER_MODELS` (root `.env`), alongside the existing `deepseek-v4-pro-260425`.
- Introduce three tier-alias env vars — `LEADER_MODEL_HIGH`, `LEADER_MODEL_BALANCE`, `LEADER_MODEL_FAST` — each naming a `LEADER_MODELS` entry. Tiers are the new preferred way to reference a model by role rather than by concrete name.
- `specialist_agents.model` and `workflow_steps.model` SHALL accept a tier alias (`high` / `balance` / `fast`) in addition to a concrete `LEADER_MODELS` name or `null`. A new `list_model_tiers()` MCP tool resolves and lists the configured tiers.
- `run_workflow` / `run_workflow_step`: a step whose `model` is `null` SHALL default to the `fast` tier (the common data-fetch case). A step may opt into `high` for complex reasoning by setting `model="high"` (or a concrete strong model).
- New LLM-driven workflow-builder tool `build_workflow_from_goal(goal, name?, description?)` that calls a `high`-tier LLM to decompose a natural-language goal into an ordered set of specialist-agent steps, persists them via the existing `create_workflow` + `add_workflow_step` path, and returns the created workflow. Defaults to the `high` tier; `model` parameter optional override.
- `list_agent_models()` SHALL additionally surface the resolved tier → model mapping so callers can see which concrete model each tier resolves to.
- `seed_specialist_agents.py` updated so the default seeded agent `model` is the `fast` tier alias (rather than `null`), aligning seeded agents with the new fetch-default.

## Capabilities

### New Capabilities
- `model-tiers`: Three role-based model tiers (`high` / `balance` / `fast`) defined by env vars, each resolving to a `LEADER_MODELS` entry, with a resolver usable by agents, steps, and tools. Tier aliases are accepted wherever a `model` is accepted today.
- `workflow-builder`: An LLM-driven `build_workflow_from_goal` tool that turns a natural-language goal into a persisted workflow of specialist-agent steps, defaulting to the `high` tier.

### Modified Capabilities
- `crewai-data-workflow`: Step/agent `model` resolution now accepts tier aliases; a step with `model=null` defaults to the `fast` tier at execution time (was: shared `LLM_*` fallback). Seeded agents default to `fast`. `list_agent_models` also returns tier mappings.

## Impact

- **Code**: `mcp/leader-mcp/specialist_agents.py` (tier resolver + `_resolve_model` accepts alias; `list_agent_models` returns tiers), `workflow_tools.py` (default-model resolution in `run_workflow`/`run_workflow_step`; new `build_workflow_from_goal` + `list_model_tiers` tools registered in `server.py`), `seed_specialist_agents.py` (default `model="fast"`), `server.py` (register 2 new tools).
- **Config**: root `.env` gains `deepseek-v4-flash` + `glm-5.2` in `LEADER_MODELS` and three `LEADER_MODEL_*` tier vars. `mcp/leader-mcp/.env` unchanged.
- **Schema**: no DB migration — tier resolution is env-driven and the existing nullable `model` column on `specialist_agents` / `workflow_steps` already holds either a concrete name or an alias string.
- **Behavior**: existing workflows with explicit concrete `model` values are unaffected; workflows relying on `null` (shared fallback) now resolve to `fast` instead of `LLM_MODEL` — a deliberate cost change, documented as the intent of this change.
- **Dependencies**: none new. `build_workflow_from_goal` reuses the existing CrewAI / direct-fallback LLM path; when CrewAI or the `high` model is unconfigured it SHALL fall back to a deterministic direct router that emits a best-effort single-step workflow (never raises).
