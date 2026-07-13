---
name: fd-daas-entities-collection-creator
description: Create a named entity collection (watchlist/portfolio of stocks + countries) driven by a membership rule - and, when the rule needs cross-table or dynamic logic the declarative JSON cannot express, author a Python rule script whose path is stored in the database so the rule can be re-run. Use this skill whenever the user wants to define a membership-rule-based group of entities - phrases like "建一个沪深300的 collection", "create a watchlist of stocks with block trades today", "group stocks by a rule", "create a portfolio that updates itself", "stocks whose close went up 3 days in a row -> collection", or any entities + "collection / watchlist / 专题 / 组合 / 集合 / 动态 / 规则 / rule / script". Use this skill when membership is described as a *condition* ("stocks whose...", "stocks in the ... table") rather than a static list - that signals a Python rule script is needed. Do NOT use this skill for ad-hoc add/remove/sync/view of an existing collection (use fd-daas-entities-collection). Uses sqlite3 on daas.db - NO MCP tools, NO cron.
---

# fd-daas-entities-collection-creator

Define a named entity collection whose membership is driven by a rule. When the rule is a simple attribute filter, use the declarative `rule_json`. When it needs to read *other* daas.db tables (today's block-trade table, an `observations` series, another collection), author a **Python rule script**; its path is stored in `entity_collections.rule_script` so a sync can re-run it.

## daas.db location

`DAAS_DATABASE_URL` in the repo-root `.env` (currently `sqlite:///daas.db`). From repo root, `sqlite3 daas.db "..."` works.

## Mental model

1. **Propose** -> collection name + condition + rule kind (`rule_json` or `rule_script`). Confirm.
2. **Author the rule** -> JSON, OR a `members(ctx)` script saved to a repo-root-relative path.
3. **Create the collection** -> `sqlite3` INSERT into `entity_collections` with the rule or `rule_script` path.
4. **Sync** -> populate membership from the rule; surface the member list. (No cron - re-sync manually.)
5. **No cron** - the scheduler is gone. Document manual re-sync.

## Step 1 - Propose the collection + rule kind

1. Collect a `name` (kebab-case) + optional `description`.
2. Elicit the **membership condition**. Decide rule kind:
   - **`rule_json`** if it's a static attribute filter on `entities` (`entity_type`/`exchange`/`country_code`/`codes`/`name_regex`, AND-combined).
   - **`rule_script`** if it reads another table or computes over data.
3. Show the proposal (name + rule kind + rule body). Ask: "Create this collection with this rule?" **Gate** - don't proceed until confirmed.

## Step 2 - Author the rule

### 2a. Declarative `rule_json`

```json
{"entity_type":"stock","exchange":"SSE","codes":["600519","600036"],"name_regex":"银行$"}
```

`name_regex` uses Python `re.search` (a REGEXP function is registered on the daas engine).

### 2b. Python `rule_script`

Write a file to a stable repo-root-relative path, e.g. `rules/entity_collections/<name>.py`. The script MUST define a top-level `members(ctx)`:

```python
def members(ctx):
    # ctx.query(sql, params=()) -> list[dict]; read-only.
    rows = ctx.query("SELECT code FROM entities WHERE entity_type='stock' AND exchange='SSE'")
    return [r["code"] for r in rows]
```

Returned items: a `str` (code, defaults to `stock`), `{"entity_type","code"}`, `{"entity_id":int}`, or an `int`. Unknown codes are skipped (not fatal). Return the **full intended set** each run - the sync diffs it. Scripts are read-only (`mode=ro`).

> **Note:** the script runner that provides `ctx` lives at `fd-daas-mcp/daas-mcp/entity_rule_script.py` and is invoked by the `daas_sync_entity_collection` tool on the `fd-daas-mcp` server/CLI: `fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli daas sync_entity_collection name=<name> --json`. (The standalone `entity_collection_sync.py` has a known `models`-import limitation outside the server.) To sync without the CLI, run the script's `members()` logic manually against `sqlite3` reads and apply the diff via the add/remove pattern in `fd-daas-entities-collection` Step 4.

## Step 3 - Create the collection

```bash
# declarative
sqlite3 daas.db "INSERT INTO entity_collections (name, description, rule_json) VALUES ('<name>', '<desc>', '<json string>')"
# script
sqlite3 daas.db "INSERT INTO entity_collections (name, description, rule_script) VALUES ('<name>', '<desc>', 'rules/entity_collections/<name>.py')"
```

`rule` and `rule_script` are mutually exclusive. **Duplicate name**: UNIQUE constraint fails - offer to update the existing collection's rule instead.

## Step 4 - Sync + surface the members

Re-derive the intended member set from the rule, diff vs current members, apply add_in/remove_out (`source='cron'`) per the `fd-daas-entities-collection` Step 4 pattern.

- **`rule_json`**: run the filter (`SELECT id FROM entities WHERE <filter>`) to get intended ids.
- **`rule_script`**: run the script's `members(ctx)` logic against `sqlite3` reads to get intended ids.

Then surface: `SELECT e.code, e.name, e.exchange FROM entity_collection_items i JOIN entities e ON e.id=i.entity_id WHERE i.collection_id=(SELECT id FROM entity_collections WHERE name='<name>') ORDER BY i.sort_order`.

**Empty result**: the rule matched nothing. Debug by re-reading the rule's query against `sqlite3`. Don't declare success on an empty collection.

## Step 5 - No cron

There is no scheduler. Tell the user: "To refresh membership, re-run the sync (Step 4) manually." A future change may add a minimal `crontab` entry.

## Gotchas

- **`rule_json` vs `rule_script` is the first decision.** `rule_json` filters `entities` only; it can't read `observations`/`scraw_*`/another collection. If the condition references any other table, it must be a script.
- **The script path is repo-root relative.** Pass `rules/entity_collections/<name>.py`, not an absolute path.
- **`members(ctx)` must return the full intended set every run**, not a delta. The sync computes the diff.
- **Scripts are read-only.** Don't persist from the script.
- **No cron.** Don't promise scheduled refresh.
- This skill stops at collection + rule. For hand add/remove/history/discovery, use `fd-daas-entities-collection`.
