## Context

`leader-mcp`'s crewai-data-workflow layer resolves LLMs through `LEADER_MODELS` (a JSON env of named model specs) with a shared `LLM_*` fallback. `build_llm(model_name)` in `specialist_agents.py` is the single resolution chokepoint: a named entry → CrewAI `LLM`; `null` → shared fallback; missing name → hard error; missing creds → soft fallback to `_direct_fetch`. `run_specialist_step(agent, request, model_override=step.get("model"))` passes the step's `model` straight through, so a `null` step model lands on the shared `LLM_MODEL` (`deepseek-v4-pro-260425` today). There is no notion of model *roles* (cheap vs. strong), and no way to generate a workflow from a goal — workflows are assembled by hand via `create_workflow` + `add_workflow_step`. Two new models (`deepseek-v4-flash`, `glm-5.2`) need to land in `.env`.

## Goals / Non-Goals

**Goals:**
- A `high` / `balance` / `fast` tier abstraction over `LEADER_MODELS`, referenced by role.
- Data-fetch workflow steps default to `fast`; complex planning defaults to `high`.
- A new `build_workflow_from_goal` LLM tool (high tier) that emits a persisted workflow.
- `deepseek-v4-flash` + `glm-5.2` registered in `.env`; tier vars wired to concrete entries.
- Tier aliases accepted everywhere a `model` is accepted today (agents + steps).

**Non-Goals:**
- No DB schema change / migration — the existing nullable `model` text column holds aliases.
- No change to `process-mcp`'s `PROCESS_MODELS` (parallel but out of scope here).
- No removal of concrete model names — tiers are an additional layer, not a replacement.
- No tier-based routing *inside* a single step (a step uses one model for its whole run).

## Decisions

### D1: Tiers as env-var aliases, not embedded in `LEADER_MODELS`
Three env vars — `LEADER_MODEL_HIGH`, `LEADER_MODEL_BALANCE`, `LEADER_MODEL_FAST` — each hold a `LEADER_MODELS` entry *name*. The tier resolver maps `fast` → `LEADER_MODEL_FAST` → entry name → `build_llm`.
- **Why**: keeps `LEADER_MODELS` as pure model specs; tiers are role assignment swappable without touching model credentials. Adding/removing a model is independent of which role it plays.
- **Alt considered**: a `tier` field inside each `LEADER_MODELS` entry. Rejected — couples role to spec, and a model could plausibly serve two roles.

### D2: Resolve tiers inside `build_llm` (single chokepoint)
`build_llm(model_name)` treats `high`/`balance`/`fast` as aliases: resolve to concrete name first, then proceed exactly as today. All callers (specialist agents, workflow steps, the new builder) inherit tier support with no per-call-site logic.
- **Why**: one place to maintain; preserves the existing hard-error / soft-fallback contract.
- **Alt considered**: resolve at each call site. Rejected — scattered, easy to miss.

### D3: `null` step model → `fast` tier (was: shared `LLM_*` fallback)
In `run_workflow` / `run_workflow_step`, when `step.get("model")` is `None`, pass `"fast"` to `run_specialist_step` instead of `None`. Steps with an explicit concrete model or explicit tier are untouched.
- **Why**: data fetching is the common workload and the cheapest model is the right default; the shared `LLM_MODEL` (`deepseek-v4-pro-260425`) is a mid-tier model being used for trivial fetches today.
- **Trade-off**: existing workflows that relied on `null` now use `fast` instead of `LLM_MODEL`. This is the intended behavior change; documented in the proposal. Explicit-model workflows are unaffected.
- **Alt considered**: add a separate `model_tier` column and leave `model=null` alone. Rejected — defeats the "fast by default" intent and adds a column for no new information.

### D4: `build_workflow_from_goal` reuses the high tier + existing persistence
New tool `build_workflow_from_goal(goal, name=None, description=None, model="high")` builds a high-tier CrewAI LLM, prompts it to decompose `goal` into an ordered list of `{agent, request, depends_on?, on_fail?}` steps against the registered specialist agents, then persists them via the existing `create_workflow` + `add_workflow_step` path. Returns the created workflow (same shape as `get_workflow`).
- **Why**: reuses validated persistence + the agent registry; the builder only adds the planning step. Defaulting to `high` matches the "complex work" intent.
- **Fallback**: when `crewai` is unavailable or the `high` model is unconfigured, the builder SHALL fall back to a deterministic direct router that emits a single best-effort step using the first specialist agent whose upstream keyword-matches `goal` (or the first enabled agent), recorded in the workflow's metadata — never raises.
- **Validation**: steps whose `agent` is not in `specialist_agents` are rejected before persist; the LLM is re-prompted once, then the offending step is dropped with a warning rather than failing the whole build.
- **Alt considered**: a free-standing generator that bypasses `add_workflow_step`. Rejected — loses validation and idempotent sort_order handling.

### D5: New models in `.env` via `LEADER_MODELS` entries, per-entry creds optional
Root `.env` gains:
```
LEADER_MODELS={"pro":{"model":"deepseek-v4-pro-260425"},"flash":{"model":"deepseek-v4-flash"},"glm":{"model":"glm-5.2"}}
LEADER_MODEL_HIGH=glm
LEADER_MODEL_BALANCE=pro
LEADER_MODEL_FAST=flash
```
Per-entry `base_url`/`api_key` are optional (fall back to shared `LLM_*`). `glm-5.2` is reachable via the same Volcengine Ark endpoint in this deployment; if a different provider is needed, the entry can carry its own `base_url`/`api_key`/`provider`.
- **Why**: matches the existing `LEADER_MODELS` shape and the `load_models()` fallback logic already in place — minimal code change.
- **Alt considered**: three separate `*_API_KEY` env vars per model. Rejected — `LEADER_MODELS` already centralizes this.

### D6: `list_agent_models` + new `list_model_tiers` expose the mapping
`list_agent_models()` additionally returns a `tiers` object `{high, balance, fast}` → resolved model name. A new `list_model_tiers()` tool returns just the tier mapping (alias → entry → concrete model + provider + vision). Both are read-only and cache-safe.
- **Why**: callers need to see what a tier resolves to before pinning a step to it.

## Risks / Trade-offs

- **[Behavior change] `null`-model steps now use `fast`, not `LLM_MODEL`.** → Documented as the intent; existing workflows with explicit models unaffected; re-run `seed_specialist_agents.py` to opt seeded agents into `fast` explicitly.
- **[Misconfig] Tier env var points at a missing `LEADER_MODELS` entry.** → Resolver returns a hard error (`"tier 'fast' → 'flash' not in LEADER_MODELS"`) which surfaces as the step's error (no fetch, no silent fallback), mirroring the existing named-model-not-configured contract.
- **[Builder quality] LLM emits an invalid agent name or unparseable step.** → Validate `agent` against `specialist_agents` before persist; drop invalid steps with a warning after one re-prompt; never raise.
- **[Builder unconfigured] No `high` model / no CrewAI.** → Deterministic direct router emits a single best-effort step; recorded in metadata; workflow still persists and runs.
- **[Cost] `fast` default may be too weak for some fetches that need tool-selection reasoning.** → Callers can still set `model="balance"` or `"high"` per step; the default is tunable via env.

## Migration Plan

1. Edit root `.env`: add `flash` + `glm` entries to `LEADER_MODELS`; add the three `LEADER_MODEL_*` tier vars.
2. Ship code: tier resolver in `specialist_agents.py`; default-`fast` in `workflow_tools.py`; `build_workflow_from_goal` + `list_model_tiers` in `workflow_tools.py`, registered in `server.py`; `list_agent_models` tier field; `seed_specialist_agents.py` default `model="fast"`.
3. Re-run `uv run --directory mcp/leader-mcp python seed_specialist_agents.py` to set seeded agents to `fast`.
4. Existing workflows: no action — explicit models keep working; `null`-model steps now resolve to `fast` (intended).
5. **Rollback**: revert `.env` (remove tier vars + new entries) and the code; `null`-model steps revert to shared `LLM_*` fallback. No DB rollback needed (no schema change).

## Open Questions

- Should `balance` have any default role? **Decision: no** — only `fast` (fetch) and `high` (build/complex) have default assignments; `balance` is available for manual per-step use. Revisit if a future capability needs it.
- Should the builder auto-run the workflow after building? **Decision: no** — `build_workflow_from_goal` returns the workflow; the caller runs it explicitly via `run_workflow`. Keeps build and execute decoupled.
