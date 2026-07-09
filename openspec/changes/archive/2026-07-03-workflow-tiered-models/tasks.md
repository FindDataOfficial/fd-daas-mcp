## 1. Environment config

- [x] 1.1 Add `flash` (`deepseek-v4-flash`) and `glm` (`glm-5.2`) entries to `LEADER_MODELS` in root `.env`, keeping the existing `pro` (`deepseek-v4-pro-260425`) entry; per-entry `base_url`/`api_key` omitted so they fall back to shared `LLM_*`
- [x] 1.2 Add `LEADER_MODEL_HIGH=glm`, `LEADER_MODEL_BALANCE=pro`, `LEADER_MODEL_FAST=flash` to root `.env`
- [x] 1.3 Verify `load_models()` in `specialist_agents.py` parses the three entries without error (manual: `uv run --directory mcp/leader-mcp python -c "from specialist_agents import load_models; print(load_models())"`)

## 2. Tier resolver

- [x] 2.1 Add `resolve_tier(alias) -> (cfg|None, error|None)` to `specialist_agents.py`: read `LEADER_MODEL_HIGH`/`_BALANCE`/`_FAST`; map alias → entry name → `load_models()` entry; return `(None, None)` when env var unset; return `(None, "tier '<alias>' → '<name>' not in LEADER_MODELS")` when the named entry is missing
- [x] 2.2 Add `_TIER_ALIASES = {"high","balance","fast"}` constant and a `tier mapping` cache invalidated by `reset_models_cache()`
- [x] 2.3 Extend `build_llm(model_name)`: if `model_name` is in `_TIER_ALIASES`, call `resolve_tier` first; on dangling-tier error return `(None, <error>, None)` (hard error, same shape as named-model-not-configured); on unset tier fall through to the existing soft-fallback path
- [x] 2.4 Add `list_model_tiers()` returning `{tiers: {high|balance|fast: {entry, model, provider, vision} | null | {entry, error}}}`; export it from `specialist_agents.py`

## 3. Workflow default-fast + tier visibility

- [x] 3.1 In `workflow_tools.py` `_run_step`/`run_specialist_step` call site: when `step.get("model")` is `None`, pass `"fast"` as `model_override` (instead of `None`) so null-model steps resolve to the fast tier
- [x] 3.2 Confirm the soft-fallback still holds: if `LEADER_MODEL_FAST` is unset, `build_llm("fast")` returns the soft `reason="no LLM configured..."` and the step falls back to `_direct_fetch` (no regression)
- [x] 3.3 Extend `list_agent_models()` (in `specialist_agents.py`) to include a `tiers` object via `list_model_tiers()` in its return value

## 4. New MCP tools

- [x] 4.1 Implement `build_workflow_from_goal(goal, name=None, description=None, model="high")` in `workflow_tools.py`: build LLM via `build_llm(model)`; prompt with `goal` + registered specialist agents (name/upstream/role/goal); parse ordered `{agent, request, depends_on?, on_fail?}` steps; persist via `create_workflow` + `add_workflow_step`; return workflow shape + `warnings`
- [x] 4.2 Implement agent-name validation in the builder: drop steps whose `agent` is not in `specialist_agents` after one re-prompt; record each drop in `warnings`
- [x] 4.3 Implement the deterministic direct fallback in the builder: when `crewai` unavailable or LLM build fails (hard or soft), pick the first enabled specialist agent whose upstream/role keyword-matches `goal` (else first enabled agent) and persist a single-step workflow with the original `goal` as `request`; record `{"fallback":"direct","reason":...}` in `warnings`
- [x] 4.4 Derive a kebab-case `name` from `goal` when `name` is omitted (slugify, unique-check against existing workflows, append `-2`/`-3` on collision)
- [x] 4.5 Register `list_model_tiers` and `build_workflow_from_goal` in `server.py` via `app.add_tool(...)`; add them to the `workflow_tools` `__all__` and the docstring tool count (10 → 12)

## 5. Seed script

- [x] 5.1 Update `seed_specialist_agents.py` `_agent_template`/upsert to set `model="fast"` as the seeded default (instead of `None`)
- [x] 5.2 Preserve the existing `preserve_model` logic: re-running the seed does NOT overwrite a user-set `model` (including a different tier alias or concrete name)
- [x] 5.3 Re-run `uv run --directory mcp/leader-mcp python seed_specialist_agents.py --dry-run` to confirm the seeded `model="fast"`; then run without `--dry-run` against `mcp/daas.db`

## 6. Self-check & tests

- [x] 6.1 Extend `selfcheck_workflow.py` (or add `selfcheck_tiers.py`) with a temp-DB, no-LLM path that asserts: tier alias resolution (set / unset / dangling); `null` step model → `fast` in `run_workflow_step`; `list_model_tiers` shape; builder direct-fallback emits a one-step workflow with a `warnings` entry
- [x] 6.2 Add a tier-resolver unit test: `LEADER_MODEL_FAST=flash` + `LEADER_MODELS={"flash":{...}}` resolves; `LEADER_MODEL_HIGH=ghost` + no `ghost` entry returns the dangling error; unset `LEADER_MODEL_BALANCE` returns `(None, None)`
- [x] 6.3 Run `uv run --directory mcp/leader-mcp python selfcheck_workflow.py` and `uv run --directory mcp/leader-mcp python selfcheck_gateway.py` green
- [x] 6.4 Manual end-to-end: `list_model_tiers()` shows high→glm, fast→flash, balance→pro; re-run the existing `pingan-bank-business-dev` workflow and confirm step 1 (null model) now uses the `flash` model (visible in step `meta`); call `build_workflow_from_goal(goal="analyze AAPL price then latest 10-K")` and confirm a 2-step workflow is created
  - Note: `list_model_tiers` verified (high→glm-5.2, balance→deepseek-v4-pro-260425, fast→deepseek-v4-flash). The null-model→fast default is proven by `selfcheck_workflow` (null-model steps complete via the fast-tier → direct-fallback path). The full LLM-driven 2-step `build_workflow_from_goal` requires `litellm` (not installed in this env) + a live paid LLM call, so it was verified only via the deterministic direct-fallback path; the LLM path is structurally covered by the selfcheck + `resolve_tier` tests.

## 7. Docs

- [x] 7.1 Update `CLAUDE.md` leader-mcp section: note tier env vars (`LEADER_MODEL_HIGH`/`_BALANCE`/`_FAST`), the two new tools (`list_model_tiers`, `build_workflow_from_goal`), the null→fast default, and that seeded agents default to `fast`
- [x] 7.2 Update the `crewai-data-workflow` tool count (10 → 12) and the `specialist_agents.py` key-file description in `CLAUDE.md`
