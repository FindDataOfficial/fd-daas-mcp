## ADDED Requirements

### Requirement: Model tier registry

The system SHALL support three model-tier aliases — `high`, `balance`, `fast` — each mapped to a named `LEADER_MODELS` entry by the env vars `LEADER_MODEL_HIGH`, `LEADER_MODEL_BALANCE`, and `LEADER_MODEL_FAST` respectively. A tier resolver SHALL map an alias to its configured `LEADER_MODELS` entry name, then to the entry's model spec, in one step. A tier alias whose env var is unset SHALL resolve to `None` (treated as "no tier configured"). A tier alias whose env var names an entry NOT present in `LEADER_MODELS` SHALL be a hard configuration error: the resolver SHALL return a clear error string naming both the alias and the missing entry, WITHOUT making a network call. The resolver SHALL be cached after first use and invalidated by `reset_models_cache()`.

#### Scenario: Tier alias resolves to a concrete model
- **WHEN** `LEADER_MODEL_FAST=flash` and `LEADER_MODELS={"flash":{"model":"deepseek-v4-flash"}}` are set and the resolver is called with alias `fast`
- **THEN** the resolver returns the `flash` entry's spec (model `deepseek-v4-flash`, base_url, api_key, provider, vision)

#### Scenario: Tier env var unset resolves to None
- **WHEN** `LEADER_MODEL_BALANCE` is unset and the resolver is called with alias `balance`
- **THEN** the resolver returns `None` (no hard error)

#### Scenario: Tier env var pointing at a missing entry is a hard error
- **WHEN** `LEADER_MODEL_HIGH=glm` and `glm` is not a key in `LEADER_MODELS` and the resolver is called with alias `high`
- **THEN** the resolver returns an error string `tier 'high' → 'glm' not in LEADER_MODELS` and makes no network call

### Requirement: Tier alias acceptance on model fields

Wherever a `model` parameter is accepted today — `specialist_agents.model`, `workflow_steps.model`, and the `model` parameter of `build_workflow_from_goal` — the value SHALL be one of: a tier alias (`high` / `balance` / `fast`), a concrete `LEADER_MODELS` entry name, or `null`. A tier alias SHALL be resolved to its concrete model spec before the LLM is built, using the model tier registry. A concrete entry name SHALL resolve exactly as today. The alias resolution SHALL happen inside the existing `build_llm` chokepoint so all callers inherit it.

#### Scenario: Specialist agent model set to a tier alias
- **WHEN** `create_specialist_agent(name="edgar-agent", upstream="edgartools", role="...", goal="...", model="fast")` is called and `LEADER_MODEL_FAST=flash` resolves to a configured `LEADER_MODELS` entry
- **THEN** the agent row is persisted with `model="fast"` (the alias string, not the resolved name)
- **AND** when the agent runs a step, `build_llm("fast")` resolves the alias and builds the CrewAI LLM from the `flash` entry

#### Scenario: Workflow step model set to a tier alias
- **WHEN** `add_workflow_step(workflow_name="w", agent="edgar-agent", request="...", model="high")` is called and `LEADER_MODEL_HIGH=glm` is configured
- **THEN** the step row is persisted with `model="high"`
- **AND** at run time the step's LLM is built from the `glm` entry

#### Scenario: Tier alias resolution failure surfaces as a step error
- **WHEN** a step has `model="fast"` and `LEADER_MODEL_FAST` names an entry not in `LEADER_MODELS`
- **THEN** the step returns `{"error": "tier 'fast' → '<name>' not in LEADER_MODELS"}` without any network call
- **AND** the run records that step as `failed` and continues or stops per the step's `on_fail` policy

### Requirement: list_model_tiers tool

A `list_model_tiers()` MCP tool SHALL return the resolved tier mapping as `{tiers: {high: {entry, model, provider, vision} | null, balance: {...} | null, fast: {...} | null}}`. An unset tier SHALL appear with value `null` (not an error). A tier whose entry is missing from `LEADER_MODELS` SHALL appear with an `error` field naming the dangling entry. The tool SHALL be read-only and SHALL NOT spawn any upstream subprocess.

#### Scenario: list_model_tiers returns all three tiers
- **WHEN** `LEADER_MODEL_HIGH=glm`, `LEADER_MODEL_FAST=flash` are set and `LEADER_MODEL_BALANCE` is unset, and `LEADER_MODELS` contains `glm` and `flash` entries
- **THEN** `list_model_tiers()` returns `{tiers: {high: {entry:"glm", model:"glm-5.2", ...}, balance: null, fast: {entry:"flash", model:"deepseek-v4-flash", ...}}}`

#### Scenario: list_model_tiers flags a dangling tier
- **WHEN** `LEADER_MODEL_HIGH=ghost` and `ghost` is not in `LEADER_MODELS`
- **THEN** `list_model_tiers()` returns a `tiers.high` entry of `{entry:"ghost", error:"not in LEADER_MODELS"}` rather than `null`
