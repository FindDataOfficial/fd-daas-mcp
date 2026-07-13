---
name: fd-daas-datasource-builder
description: >
  Analyze a Python data-library project (local path or GitHub URL) and auto-generate
  a daas-ready datasource: discover its data-fetching functions, infer parameters /
  fields / update-frequency / data-source / confidence / entities, propose indicators
  per field (deduped against daas.db), add a sidecar Click CLI for functions that lack
  one, and emit a skill doc so AI can fetch data from the library. Use this skill
  whenever the user wants to onboard or integrate a Python data source (akshare /
  yfinance / edgar / … or any new GitHub data lib) into daas, generate a daas
  descriptor JSON, build a CLI wrapper for a project's functions, or "turn this
  project into a daas datasource". Trigger hard on phrases like "analyze this data
  lib", "make a daas descriptor for X", "add a CLI to this project's functions",
  "onboard source Y from github", "generate indicators/entities for this library",
  "给这个项目的函数加 cli", "接入 daas", "生成 descriptor".
---

# fd-daas-datasource-builder

Turn a Python data library into a daas-ready datasource. Given a **local project path** or a **GitHub URL**, this skill produces three artifacts that ship alongside the project (the original project is never modified):

1. **`daas.descriptor.json`** — a daas.db-schema-mirrored descriptor (`source` + `daas_functions` + `daas_function_columns` + proposed `indicator_rules` + entity coverage) that can be imported into `daas.db` with one command.
2. **`daas_cli.py`** — a sidecar Click CLI exposing the library's data-fetching functions that don't already have a CLI. It imports the original package; it does not touch upstream code.
3. **`daas-skill/SKILL.md`** — a mini skill doc (+ dispatch entry) so an AI agent can call the library to fetch data and persist it.

The intelligence (inferring frequency / source / confidence / entities / indicator proposals) is the agent's job, guided by the rubrics in `references/`. The scripts do the deterministic heavy lifting (AST discovery, daas.db dedup, schema validation, CLI generation, import).

## When to use

- "把这个 GitHub 数据库接入 daas / onboard akshare / 分析 yfinance 生成 descriptor"
- "给这个项目的函数加个 CLI / 给没有 cli 的 function 生成 cli"
- "为这个库生成 indicators 和 entities / 推测数据来源和更新频率 / 给数据置信度评分"
- "生成一个 skill 文档让 AI 能用这个库取数"

Do NOT use for: scraping a website into `scraw_*` (use `fd-daas-scrapling-official`), building dashboards (`fd-daas-dashboard-creator`), or fetching data from a source that's already onboarded (`skill-based-data-fetch`).

## Inputs

- `PROJECT` — a local path to a Python project root, or a `https://github.com/...` URL (cloned to a temp dir first).
- `SOURCE_NAME` (optional) — the daas source name (e.g. `akshare`). Inferred from the package/repo name if omitted.
- `OUTPUT_DIR` (optional, default = project root) — where to write the three artifacts.
- `SCOPE` (optional) — a list of function names to restrict analysis to (for huge libs like akshare, analyze only the named functions).

## The daas.db location

Read `DAAS_DATABASE_URL` from the repo-root `.env`. The DB is at repo-root `daas.db` today. Use it to (a) dedup proposed indicators against existing `indicator_rules.indicator_name`, and (b) match entities against the `entities` table.

```bash
DB=$(grep -i '^DAAS_DATABASE_URL=' "$(git rev-parse --show-toplevel)/.env" | cut -d= -f2- | tr -d '"' | sed 's|sqlite:///||')
```

## Workflow

### Step 1 — Acquire the project

If `PROJECT` is a GitHub URL:
```bash
git clone --depth 1 <url> /tmp/<repo-name>
```
If a local path, use it in place. Confirm the Python package root (the dir you `import` from) — look for `pyproject.toml` / `setup.py` and the top-level package dir. This becomes `--package` / `--import-root` later.

### Step 2 — Discover data-fetching functions (deterministic)

```bash
uv run python .claude/skills/fd-daas-datasource-builder/scripts/analyze_project.py <project-root> [--package <pkg>] [--min-score 0.3] > analysis.json
```

Read `analysis.json`. Each candidate has: `function`, `module`, `qualname`, `params` (name + annotation + default + required), `return_type`, `docstring`, `signals` (name / network / return / doc heuristics), `signal_score`, `has_existing_cli`, `file`, `lineno`.

- **Drop candidates with `signal_score < 0.3`** — they're not data fetchers.
- Apply `SCOPE` if given: keep only candidates whose `function` is in the scope list.
- The sidecar CLI (Step 7) wraps only candidates with `has_existing_cli == false`.

### Step 3 — Pull existing daas.db names for dedup (deterministic)

```bash
uv run python .claude/skills/fd-daas-datasource-builder/scripts/match_existing.py > existing.json
```

`existing.json` holds: existing `indicator_name`s, existing `source` names, and an `entity_sample` (codes per `entity_type`). You'll consult this in Steps 4–5 to avoid duplicates and flag new concepts/entities.

### Step 4 — Infer per-function metadata (LLM, guided by rubric)

For each surviving candidate, read its docstring + signature + (if cheap & keyless) a dry-run sample (`uv run --with <deps> python -c "import ...; print(df.columns.tolist(), df.dtypes)"`), then infer — following `references/indicator-and-confidence-rubric.md`:

- **category** — stocks / macro / reference / news / fund / bond / crypto / … (from name grouping + docstring).
- **parameters** — `{name, type, required, description, default}`. Types from annotations, descriptions from docstring.
- **columns** — the fields the function returns. Infer `name / label / type / description / nullable` from docstring, return-type hints, or a dry-run `df.columns` / `df.dtypes`. If columns can't be determined, set `columns: []` and lower `confidence`.
- **frequency** — `realtime / intraday / daily / weekly / monthly / quarterly / annual / irregular` (keyword map in the rubric).
- **data_provenance** — the upstream source (official bureau / exchange / aggregator) from docstring / README.
- **confidence** (0–1) — weighted rubric in the rubric reference. Always record `confidence_reasoning` citing the dimensions.
- **entities** — which entity types this function covers + the identifier shape (e.g. stock → 6-digit code; country → ISO alpha-2). For each, set `matched_existing` by checking `existing.json.entity_sample[entity_type]` has members plausibly covering this source's identifiers; if not, `matched_existing=false` + a `note`.

### Step 5 — Propose indicators per field (LLM, dedup vs daas.db)

For each column that is a **numeric time-series metric** (has a date/index axis), propose `indicator_rules` using the ops in `run_indicator.py`: `sma / ema / rsi / pct_change / log_return / zscore / rolling_std / rolling_min / rolling_max / ratio / diff / level`. Don't propose every op for every field — pick relevant ones (price-like → sma/ema/rsi; macro flow → pct_change/zscore; snapshot → level). For each proposal:

- `name` = `indicator_name` = `<SOURCE>_<func>_<field>_<op><window>` (lowercase; e.g. `tiny_econ_get_cpi_series_cpi_yoy_sma5`).
- `value_column` / `date_column` from the columns; `source_table` = `scraw_<source>_<func_slug>`; `datasource` = SOURCE_NAME; `function_name` = the function name.
- Check `existing.json.indicator_names`: if the proposed `indicator_name` already exists → `dedup_status: "exists"`. Else → `"new"`.
- **New-concept flag**: if the field is a metric whose concept is NOT represented anywhere in daas today (e.g. GDP / CPI / population — the existing indicators are all price/return technicals), set the column's `indicator_match: "candidate_new_metric"` with a `note` describing the concept, and mark its proposals `dedup_status: "new_concept"`.

Non-metric fields (date axis, identifier, text, code) → `indicator_match: "not_a_metric"` + a `note`; no `proposed_indicator_rules`.

### Step 6 — Emit & validate the descriptor

Assemble `daas.descriptor.json` following `references/descriptor-schema.md` (mirrors daas.db: a top-level `source` + `daas_functions[]`, each carrying `parameters[]`, `columns[]` with their `proposed_indicator_rules[]`, `entities[]`, plus `frequency`, `confidence`, `confidence_reasoning`, `data_provenance`, `has_existing_cli`). Then validate:

```bash
uv run python .claude/skills/fd-daas-datasource-builder/scripts/validate_descriptor.py daas.descriptor.json
```

**Fix every error before continuing.** The descriptor must round-trip into daas.db without manual edits.

### Step 7 — Generate the sidecar CLI

```bash
uv run python .claude/skills/fd-daas-datasource-builder/scripts/gen_cli.py daas.descriptor.json --import-root <pkg> --out daas_cli.py
```

This writes `daas_cli.py` — a Click CLI with one command per function where `has_existing_cli == false`, params from the descriptor, output as JSON records (DataFrame → `to_json(orient="records")`). It imports the original package via `importlib` (no modification). Smoke-test it:

```bash
uv run --with <deps> python daas_cli.py --help
# and one cheap, keyless command if available
```

### Step 8 — Generate the skill doc

Write `daas-skill/SKILL.md` — a mini skill (<150 lines) that tells an AI how to fetch data from this library: the import shape, one example call per category, how to persist to `scraw_<slug>` via the upsert script (`.claude/skills/skill-based-data-fetch/scripts/upsert.py`), and a dispatch-style entry. The descriptor is the source of truth. Also write `daas-skill/dispatch.json` with the per-function import+call snippets so it's machine-readable.

### Step 9 — Write artifacts + summarize

Write `daas.descriptor.json`, `daas_cli.py`, `daas-skill/SKILL.md`, `daas-skill/dispatch.json` into `OUTPUT_DIR` (default: the project root, so they ship with the project). Then tell the user:

- how many functions discovered / wrapped in the CLI / dropped as non-fetchers;
- proposed indicators: `new` vs `exists` vs `new_concept` counts;
- entities: matched vs new (with the notes);
- source-level `confidence` + reasoning;
- the exact commands to (a) run the CLI, (b) import the descriptor into daas.db (`scripts/import_descriptor.py`), (c) install the skill doc.

## Principles

- **Never modify the original project.** The CLI is a sidecar; the skill doc is a sibling folder. All artifacts are additive.
- **Inference is conservative.** When a field / frequency / source can't be determined, say so in a `note` rather than guessing, and lower `confidence`. The user trusts honest notes more than a confident wrong guess.
- **Dedup, don't duplicate.** Every proposed `indicator_name` and source name must be checked against `existing.json`. The value of this skill is a clean, import-ready descriptor — duplicates break the import.
- **Import-ready JSON.** The descriptor must round-trip into daas.db. `validate_descriptor.py` is the gate; `import_descriptor.py` proves it.

## References

- `references/descriptor-schema.md` — exact JSON schema (mirrors daas.db), with a full example.
- `references/indicator-and-confidence-rubric.md` — frequency keyword map, confidence rubric (5 weighted dimensions), indicator-proposal + dedup + new-concept rules.
- `scripts/analyze_project.py` — AST discovery of data-fetching functions + existing-CLI detection.
- `scripts/match_existing.py` — pull existing `indicator_name`s / `source` names / entity samples from daas.db.
- `scripts/validate_descriptor.py` — schema gate before CLI generation.
- `scripts/gen_cli.py` — sidecar Click CLI generator.
- `scripts/import_descriptor.py` — idempotent import of a descriptor into daas.db.
