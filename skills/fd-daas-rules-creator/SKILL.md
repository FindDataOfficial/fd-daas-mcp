---
name: fd-daas-rules-creator
description: Create a unified daas rule (json / script / position / llm) that derives a member set or extracts rows, persist it via daas_create_rule, optionally attach it to an entity or indicator collection, dry-run it with daas_test_rule, and sync. Use this skill whenever the user wants to define a rule that computes a group of entities/indicators or extracts structured data - phrases like "建一个规则选出沪深300的股票", "create a rule for stocks in today's block-trade table", "extract the ticker codes from this page into a collection", "用自然语言从新闻里抽公司名", "group entities by a rule", "position/css/xpath rule", "llm extraction rule", or any "rule / 规则 / 脚本规则 / 位置规则 / llm规则" + collection/extraction intent. Decide the rule TYPE first (json=static entity filter, script=Python members(ctx), position=CSS/xpath/regex/jsonpath extraction, llm=natural-language extraction). Do NOT use this skill for ad-hoc add/remove of an existing collection's members (use fd-daas-entities-collection / fd-daas-indicators-collection) or to create individual math indicators (use fd-daas-indicators-creator). Uses the fd-daas-mcp daas_create_rule/daas_test_rule/daas_run_rule tools + sqlite3 on daas.db.
---

# fd-daas-rules-creator

Author a unified daas rule of one of four types, persist it, attach it to a collection (optional), dry-run it, and sync. Rules live in the `rules` table and are evaluated by the `RuleEngine` (`fd-daas-mcp/daas-mcp/rule_engine.py`).

## daas.db location

`DAAS_DATABASE_URL` in the repo-root `.env` (currently `sqlite:///daas.db`). From repo root, `sqlite3 daas.db "..."` works. The `rules` table: `id, name UNIQUE, rule_type, target, config_json, description, enabled`.

## Mental model

1. **Propose** -> what the rule yields (`target`: `entity_ids` | `indicator_names` | `rows`) + which `rule_type`. Confirm.
2. **Author** -> the `config_json` (+ a `.py` file for `script`; a tested selector for `position`; a `prompt`+`schema_json` for `llm`).
3. **Persist** -> `daas_create_rule`.
4. **Attach** (optional) -> `daas_create_entity_collection(rule_id=…)` / `daas_create_indicator_collection(rule_id=…)`, or update an existing collection's `rule_id`.
5. **Dry-run** -> `daas_test_rule`. Debug empty results before declaring success.
6. **Sync** (for member-target rules) -> `daas_sync_entity_collection` / `daas_sync_indicator_collection`. For `target='rows'` (llm) -> `daas_run_rule` extracts into `process_results`.
7. **No cron** -> refresh is manual (re-run sync / run_rule).

See `references/rule-types.md` for the authoritative `config_json` contract + worked examples per type.

## Step 1 - Propose the rule (type + target)

Decide `rule_type`:
- **`json`** - a static attribute filter on `entities` (`entity_type`/`exchange`/`country_code`/`codes`/`name_regex`, AND-combined). `target='entity_ids'`. Use when the condition is just "all entities matching these attributes".
- **`script`** - a Python file defining `members(ctx)` that can read any daas.db table via `ctx.query(sql)` (read-only), fetch URLs via `ctx.http_get(url)`, or call the LLM via `ctx.llm(prompt, text, schema)`. Any `target`. Use for cross-table/dynamic logic, or anything the other types can't express.
- **`position`** - extract values from a structural position (CSS / xpath / regex / json-path) in a URL, file, table column, or inline text. Returns extracted strings (mapped to members per `target`). Use for "scrape this table / parse this page".
- **`llm`** - natural-language extraction from text. For `target='entity_ids'`/`'indicator_names'`, extract from inline `text` and map records to members. For `target='rows'`, incremental extraction over a `source_table`+`text_column` into `process_results` (reuses the OpenAI-compatible LLM). Use for "pull every ticker / company name mentioned in this text".

Decide `target`: `entity_ids` (drives an entity collection), `indicator_names` (drives an indicator collection), or `rows` (standalone extraction into `process_results`).

Show the proposal (name + rule_type + target + config sketch). **Gate** - don't proceed until confirmed.

## Step 2 - Author the config

Author the `config_json` per the type (see `references/rule-types.md`). For `script`, write the `.py` file to a repo-root-relative path (e.g. `rules/<...>.py`). For `position`, test the selector against the actual source (a regex/CSS that matches nothing is the common failure). For `llm`, write a tight `prompt` + a JSON Schema for the records.

## Step 3 - Persist

```
fd-daas-mcp/.venv/bin/python -m fd_daas_mcp.cli daas create_rule \
  name=<name> rule_type=<type> target=<target> config_json='<json string>' --json
```

`daas_create_rule` validates: `rule_type`/`target` are in the allowed sets; `config_json` parses; `script` rules require an existing `script_path`; `llm` rules require an existing `source_table`+`text_column` (when given). Duplicate name -> error (offer to update instead).

## Step 4 - Attach to a collection (optional, for member-target rules)

```
daas create_entity_collection name=<coll> rule_id=<rule id> --json
# or update an existing collection:
daas update_entity_collection name=<coll> rule_id=<rule id> --json
# indicator collections:
daas create_indicator_collection name=<coll> rule_id=<rule id> --json
```

`rule_id` is mutually exclusive with the legacy `rule`/`rule_script` (entity collections). An indicator collection's rule must have `target='indicator_names'`; an entity collection's rule must have `target='entity_ids'`.

## Step 5 - Dry-run

```
daas test_rule name=<name> --json
```

`daas_test_rule` evaluates WITHOUT persisting: for member targets returns the derived set; for `target='rows'` (llm) extracts a single source row as a sample. **Empty result** -> debug by re-reading the rule's query/selector/prompt against the real source. Don't declare success on empty.

## Step 6 - Sync / run

- Member targets: `daas sync_entity_collection name=<coll>` / `daas sync_indicator_collection name=<coll>` -> re-derives membership, diffs, records `add_in`/`remove_out` (`source='cron'`).
- `target='rows'` (llm): `daas run_rule name=<name>` -> incremental extraction into `process_results` (advances `config_json.last_rowid`).

Surface the result (member list / processed count).

## Step 7 - No cron

Tell the user: "To refresh, re-run the sync (or `daas_run_rule` for rows) manually." Do not promise scheduled refresh.

## Gotchas

- **Type first.** `json` only filters `entities`; it can't read other tables or fetch URLs. Cross-table / dynamic / fetch / LLM-orchestration -> `script`. Structured page/table extraction -> `position`. Natural-language extraction -> `llm`.
- **`target` must match the collection kind.** Entity collections need `target='entity_ids'`; indicator collections need `target='indicator_names'`; standalone extraction uses `target='rows'`.
- **`position` needs `lxml`+`cssselect` (css/xpath) and `jsonpath-ng` (jsonpath)** - install the `fd-daas-mcp` deps; `regex` needs nothing extra. A missing dep surfaces as a clear error, not a crash.
- **`llm` needs LLM env** (`LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` or `PROCESS_MODELS`). Unconfigured -> `{"error":...}` without a network call.
- **Scripts are read-only** (`ctx.query` opens `mode=ro`); don't persist from a script. Return the **full intended set** every run - the sync computes the diff.
- **Empty result is a bug, not success.** Always `daas_test_rule` first.
- This skill stops at rule + (optional) collection + sync. For hand add/remove/history, use `fd-daas-entities-collection` / `fd-daas-indicators-collection`.
