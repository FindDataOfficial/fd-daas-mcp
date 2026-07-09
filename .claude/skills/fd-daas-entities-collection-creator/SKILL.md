---
name: fd-daas-entities-collection-creator
description: Create a named entity collection (watchlist/portfolio of stocks + countries) driven by a membership rule — and, when the rule needs cross-table or dynamic logic the declarative JSON cannot express, author a Python rule script whose path is stored in the database so the rule can be re-run from a workflow or cron. Use this skill whenever the user wants to define a membership-rule-based group of entities — phrases like "建一个沪深300的 collection", "create a watchlist of stocks with block trades today", "把今天大宗交易过的股票存成一个 collection 并每天刷新", "group stocks by a rule", "create a portfolio that updates itself", "stocks whose close went up 3 days in a row → collection", or any entities + "collection / watchlist / 专题 / 组合 / 集合 / 动态 / 规则 / rule / script". Make sure to use this skill when the user describes membership as a *condition* ("stocks whose...", "stocks in the ... table", "stocks that appeared in today's ...") rather than a static list — that is the signal a Python rule script is needed (the declarative rule_json only filters entities by type/exchange/country/codes/name_regex against the entities table). Do NOT use this skill for ad-hoc add/remove/sync/view of an existing collection (use fd-daas-entities-collection), or to build a dashboard (use fd-daas-dashboard-creator).
---

# fd-daas-entities-collection-creator

Define a named entity collection whose membership is driven by a rule. When the rule is a simple attribute filter (exchange, country, a fixed code list, a name regex), use the declarative `rule_json`. When the rule needs to read *other* daas.db tables — today's block-trade table, an `observations` series, another collection, a `scraw_*` snapshot — author a **Python rule script**; its path is stored in `entity_collections.rule_script` so `sync_entity_collection` can re-run it from a workflow or cron without the caller re-passing the source.

## Mental model

Five steps, with an explicit confirmation gate before any daas-mcp write:

1. **Propose** → collection name + the membership condition + which rule kind (`rule_json` or `rule_script`). Get user confirmation.
2. **Author the rule** → declarative JSON, OR a `members(ctx)` Python script saved to `mcp/daas-mcp/rules/entity_collections/<name>.py`.
3. **Create the collection** → `create_entity_collection(name, description, rule=…)` or `create_entity_collection(name, description, rule_script=<path>)`. The path is now in the DB.
4. **Sync** → `sync_entity_collection(name)` to populate membership from the rule; surface the member list.
5. **Schedule (optional)** → `entity_collection_sync.py --register-cron <name>` for daily refresh, and/or note that `sync_entity_collection` is callable from a leader-mcp workflow.

Never call `create_entity_collection` before Step 1's confirmation gate.

## Step 1 — Propose the collection + rule kind

Goal: agree on the name + the membership condition + whether a script is needed, before writing anything.

1. Collect a collection `name` (kebab-case) + optional `description`. Slugify Chinese/English phrases ("动量股" → `momentum`).
2. Elicit the **membership condition** in the user's words. Then decide the rule kind:
   - **`rule_json`** if the condition is a static attribute filter on `entities`: by `entity_type` (stock/country), `exchange` (SSE/SZSE/…), `country_code`, a fixed `codes` list, or a `name_regex`. Keys are AND-combined. This is the cheap path — no script file, no cron needed unless the set drifts (codes get added/removed).
   - **`rule_script`** if the condition reads *another* table or computes over data: "stocks in today's `scraw_dzjy` block-trade table", "stocks whose `observations` value crossed X", "union/intersection of two other collections", "stocks whose close rose 3 days running". Anything `rule_json` can't say. The script gets a read-only `ctx.query(sql)` over daas.db.
3. Show the user a proposal: name + description + rule kind + the rule body (the JSON object or the planned `members(ctx)` body). Ask: "Create this collection with this rule?"
4. **Gate** — do not proceed to Step 2 until the user confirms.

**Ambiguous condition**: if you are unsure whether `rule_json` suffices, ask the user one question: "Does this rule only filter stocks by exchange/country/a fixed code list/name pattern (→ JSON), or does it need to read another table or compute over data (→ script)?" Default a vague "stocks that meet condition X involving other data" to a script.

## Step 2 — Author the rule

Goal: produce the rule body to attach at create time.

### 2a. Declarative `rule_json`

Build a JSON object with any of these keys (all optional, AND-combined):

```json
{
  "entity_type": "stock",
  "exchange": "SSE",
  "country_code": "CN",
  "codes": ["600519", "600036"],
  "name_regex": "银行$"
}
```

`name_regex` uses Python `re.search` (a REGEXP function is registered on the daas engine). Skip keys you don't need.

### 2b. Python `rule_script`

Write a file to **`mcp/daas-mcp/rules/entity_collections/<name>.py`** (the Write tool creates parent dirs). The script MUST define a top-level `members(ctx)` returning the intended member set. See `references/script-rule-contract.md` for the full contract + copy-paste examples; the essentials:

```python
def members(ctx):
    # ctx.query(sql, params=()) -> list[dict]; read-only (SQLite mode=ro).
    rows = ctx.query(
        "SELECT code FROM entities WHERE entity_type='stock' AND exchange='SSE'"
    )
    return [r["code"] for r in rows]
```

Each returned item may be:
- a `str` → a stock code (entity_type defaults to `stock`),
- a `dict` `{"entity_type": "stock", "code": "600519"}` or `{"entity_id": 123}`,
- an `int` → an entity id directly.

Items that don't resolve to a known entity are **skipped**, not fatal — so a delisted code won't fail the whole sync. Return the *full* intended set each run; the sync diffs it against current members and records add_in / remove_out.

**Scripts are read-only.** `ctx` opens its own SQLite connection in `mode=ro`; a write statement raises `OperationalError`. If your logic needs a side effect (e.g. logging), return it as data, don't try to write to daas.db from the script.

**Path stored in the DB is repo-root relative** (e.g. `mcp/daas-mcp/rules/entity_collections/my-watchlist.py`) so it resolves regardless of cwd — cron runs under `uv run --directory mcp/daas-mcp`, workflows call in-process. When you call `create_entity_collection`, pass that relative path.

## Step 3 — Create the collection

Goal: persist the collection + its rule.

1. **Declarative**: `mcp__daas-mcp__create_entity_collection(name="<name>", description="<desc>", rule="<json string>")` — `rule` is the JSON object serialized to a string.
2. **Script**: `mcp__daas-mcp__create_entity_collection(name="<name>", description="<desc>", rule_script="mcp/daas-mcp/rules/entity_collections/<name>.py")` — pass the **repo-root-relative path**, not the source.

`rule` and `rule_script` are mutually exclusive — passing both returns an error. To switch kinds later, use `update_entity_collection(rule_script=…)` (sets the script, clears the JSON) or `clear_rule=true` (manual collection).

**Duplicate name**: the tool returns `{"error": "Entity collection '<name>' already exists"}`. Offer to update the existing collection's rule instead of recreating, or pick a new name. Confirm with the user before overwriting.

**If daas-mcp is not wired into `.mcp.json`** (e.g. only leader-mcp is registered): the write path still works via the dashboard sidecar — `uv run --directory mcp/daas-mcp python collection_writer.py create-entity-collection '{"name":"<name>","description":"<desc>","rule_script":"<relative path>"}'`. Same `EntityCollectionService` underneath. Reads (verify the row, list members) work via `sqlite3 mcp/daas.db`.

## Step 4 — Sync + surface the members

Goal: populate membership from the rule and show the result.

1. `mcp__daas-mcp__sync_entity_collection(name="<name>")` → returns `{action: "synced", rule: "json"|"script", added: [...entity_ids], removed: [...], unchanged: N}`. The first sync on an empty collection adds every matched entity; `added` carries the entity ids.
2. `mcp__daas-mcp__list_entity_collection_items(collection_name="<name>")` → `{collection, count, members: [{code, name, entity_type, exchange, …}]}`. Show the user the member table (code / name / exchange / type).
3. **Empty result**: if `count == 0`, the rule matched nothing. For a script rule, dry-run it (`uv run --directory mcp/daas-mcp python entity_collection_sync.py --sync <name> --dry-run` → reports `rule_kind`, `rule_script` path, `intended_members`) and re-read the script's `members(ctx)` query against `sqlite3 mcp/daas.db` to debug. Tell the user the rule matched zero entities and show the intended count — do not declare success on an empty collection.

**Edit the rule later**: for a script rule, just rewrite the file at the stored path and re-run `sync_entity_collection(name)` — the path in the DB hasn't changed, so no `update_entity_collection` is needed. For a JSON rule, `update_entity_collection(name, rule="<new json>")`.

## Step 5 — Schedule refresh + workflow note (optional)

Goal: make the membership self-maintaining.

- **Daily cron**: `uv run --directory mcp/daas-mcp python entity_collection_sync.py --register-cron <name>` — idempotently inserts a cron-mcp `Task` + `Schedule` (`entity-collection-sync-<name>-daily`, daily off-minute cron). The schedule takes effect on the next cron-mcp start. `--unregister-cron <name>` removes it.
- **Ad-hoc / dry-run**: `entity_collection_sync.py --sync <name> [--dry-run]` runs the sync once in-process (the cron task command is `uv run --directory mcp/daas-mcp python server.py --sync-entity-collection <name>`).
- **In a leader-mcp workflow**: `sync_entity_collection` is a daas-mcp tool, so a workflow step can call it via `call_data_mcp(server="daas-mcp", tool="sync_entity_collection", arguments={"name":"<name>"})` — or `ask_data_crew("sync the <name> entity collection")`. Because the rule (and the script path) live in the DB, the workflow needs only the collection name. This is the "use it in a workflow" hook: store the rule once, then any workflow/cron can re-run it by name.

Report to the user: "Collection `<name>` created with rule=<kind>; synced to N members; cron registered (or skipped)."

## Gotchas

- **`rule_json` vs `rule_script` is the first decision.** `rule_json` filters the `entities` table only; it can't read `observations`, `scraw_*`, or another collection. If the user's condition references any other table or a computation, it must be a script. When in doubt, ask (Step 1).
- **The script path stored in the DB is repo-root relative**, not absolute. A cron run from `mcp/daas-mcp/` and an in-process workflow call resolve it against different cwds — the runner anchors relative paths to the repo root so both work. Pass `mcp/daas-mcp/rules/entity_collections/<name>.py`, not `/Users/…/x.py`.
- **A sync never fails the whole collection over one delisted code.** Unknown codes in the script's return are skipped. This also means a script with a typo'd code silently drops it — verify `intended_members` in the dry-run matches expectations.
- **`members(ctx)` must return the full intended set every run**, not a delta. The sync computes the diff (add_in / remove_out) itself; if the script returns "just the new ones", every existing member gets remove_out'd.
- **Scripts are read-only.** `ctx.query` opens `mode=ro`; writes raise. Don't try to persist anything from the script — the sync writes membership on your behalf.
- **`sync_entity_collection` records `source='cron'` for rule-driven transitions**, even on ad-hoc runs — that's by design (the audit log distinguishes rule-driven from `source='manual'` add/removes).
- **This skill stops at collection + rule + schedule.** To add/remove individual members by hand, view history, or discover entities, use `fd-daas-entities-collection`. To build a dashboard over a collection, use `fd-daas-dashboard-creator`.
