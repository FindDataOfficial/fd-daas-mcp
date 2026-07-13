---
name: fd-daas-entities-collection
description: Manage daas entities and entity collections day-to-day - discover entities (stocks/countries), list/view/create/delete collections, add/remove/reorder members, view the add-in/remove-out audit history, and re-sync rule-based collections. Use this skill whenever the user wants to operate on entities or collections WITHOUT defining a new rule - phrases like "list my collections", "show me the members of ...", "把 600519 加到 ... 集合", "remove AAPL from ...", "这个 collection 的历史变动", "sync 一下 ... collection", "daas 里有哪些股票/国家", or any entities/collections + "list / view / add / remove / members / history / sync / reorder / delete / 查 / 看 / 加 / 删 / 同步 / 排序". Use fd-daas-entities-collection-creator to define a new rule-based collection. Do NOT use this skill to define a script/rule_json membership rule from scratch (use the creator skill), or to build a dashboard (use fd-daas-dashboard-creator). Uses sqlite3 on daas.db - NO MCP tools.
---

# fd-daas-entities-collection

Operate on entities and entity collections in daas.db via **sqlite3** - discover, manage membership by hand, view history, re-sync rule-based collections. `fd-daas-entities-collection-creator` is the define-a-new-rule skill.

## daas.db location

`DAAS_DATABASE_URL` in the repo-root `.env` (currently `sqlite:///daas.db`). From repo root, `sqlite3 daas.db "..."` works.

## Step 1 - Discover entities

```bash
sqlite3 daas.db "SELECT id, entity_type, code, name, ticker, exchange, country_code FROM entities WHERE name LIKE '%比亚迪%' OR ticker LIKE '%BYD%' OR code LIKE '%002594%' OR aliases LIKE '%比亚迪%'"
sqlite3 daas.db "SELECT * FROM entity_datasource_links WHERE entity_id=<id>"
```

Browse: `sqlite3 daas.db "SELECT id, code, name FROM entities WHERE entity_type='stock' AND exchange='SSE' LIMIT 50"`. **Not found**: tell the user, suggest a looser query, stop.

## Step 2 - List / view collections

```bash
sqlite3 daas.db "SELECT c.id, c.name, c.description, c.rule_json, c.rule_script, (SELECT COUNT(*) FROM entity_collection_items i WHERE i.collection_id=c.id) AS n FROM entity_collections c ORDER BY c.id"
sqlite3 daas.db "SELECT e.code, e.name, e.entity_type, e.exchange, i.sort_order FROM entity_collection_items i JOIN entities e ON e.id=i.entity_id WHERE i.collection_id=(SELECT id FROM entity_collections WHERE name='<name>') ORDER BY i.sort_order"
```

## Step 3 - Create a manual or simple collection

```bash
# manual collection (no rule)
sqlite3 daas.db "INSERT INTO entity_collections (name, description) VALUES ('<name>', '<desc>')"
# simple rule_json collection
sqlite3 daas.db "INSERT INTO entity_collections (name, description, rule_json) VALUES ('<name>', '<desc>', '<json string>')"
```

Then Step 6 to populate a rule-based one. For a **Python rule script**, hand off to `fd-daas-entities-collection-creator`. **Duplicate name**: the UNIQUE constraint fails - offer to add to the existing collection instead.

## Step 4 - Manage membership (add / remove / reorder)

Resolve the entity id first (`SELECT id FROM entities WHERE code='<code>' AND entity_type='stock'`). `PRAGMA foreign_keys=ON` is required for the FK to `entities`.

```bash
# add (records an add_in audit event)
sqlite3 daas.db "INSERT INTO entity_collection_items (collection_id, entity_id, sort_order) VALUES ((SELECT id FROM entity_collections WHERE name='<name>'), <entity_id>, (SELECT COALESCE(MAX(sort_order),0)+1 FROM entity_collection_items WHERE collection_id=(SELECT id FROM entity_collections WHERE name='<name>')))"
sqlite3 daas.db "INSERT INTO entity_collection_changes (collection_id, entity_id, action, source, reason) VALUES ((SELECT id FROM entity_collections WHERE name='<name>'), <entity_id>, 'add_in', 'manual', '<reason>')"
# remove (records a remove_out event)
sqlite3 daas.db "DELETE FROM entity_collection_items WHERE collection_id=(SELECT id FROM entity_collections WHERE name='<name>') AND entity_id=<entity_id>"
sqlite3 daas.db "INSERT INTO entity_collection_changes (collection_id, entity_id, action, source, reason) VALUES ((SELECT id FROM entity_collections WHERE name='<name>'), <entity_id>, 'remove_out', 'manual', '<reason>')"
```

**Reorder**: `UPDATE entity_collection_items SET sort_order=? WHERE id=?` for each item id (fetch the item ids first). The set must match exactly. **List items**: `SELECT i.id, e.code, e.name, i.sort_order FROM entity_collection_items i JOIN entities e ON e.id=i.entity_id WHERE i.collection_id=(SELECT id FROM entity_collections WHERE name='<name>') ORDER BY i.sort_order`.

## Step 5 - View the audit history

```bash
sqlite3 daas.db "SELECT ch.changed_at, ch.action, ch.source, ch.reason, e.code, e.name FROM entity_collection_changes ch JOIN entities e ON e.id=ch.entity_id WHERE ch.collection_id=(SELECT id FROM entity_collections WHERE name='<name>') ORDER BY ch.changed_at DESC LIMIT 20"
```

`source=manual` = hand add/remove; `source=cron` = rule-driven sync.

## Step 6 - Sync a rule-based collection

The sync logic (rule re-evaluation + add_in/remove_out diff) lives at `fd-daas-mcp/daas-mcp/` (`entity_collection_sync.py` + `entity_rule_script.py`) and is exposed as the `daas_sync_entity_collection` tool on the `fd-daas-mcp` server/CLI - the working automated path:

```bash
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli daas sync_entity_collection name=<name> --json
```

The standalone `entity_collection_sync.py` has a known `models`-import limitation when run outside the server, so prefer the CLI above. This skill is no-MCP-tools, so you can also sync manually via `sqlite3`:
- **`rule_json` collections**: re-derive by running the JSON filter against `entities` yourself (e.g. `SELECT code FROM entities WHERE exchange='SSE'`), diff vs current members, and add/remove per Step 4 with `source='cron'`.
- **`rule_script` collections**: run the script's `members(ctx)` logic manually against `sqlite3` reads, diff, and apply.
- **Manual collection**: no-op.

## Step 7 - Delete

```bash
sqlite3 daas.db "DELETE FROM entity_collections WHERE name='<name>'"
```

Cascades to `entity_collection_items` + `entity_collection_changes` (FK CASCADE). Confirm first - irreversible. Does NOT delete the rule script file on disk - `rm` it explicitly if `rule_script` was set.

## Gotchas

- **Resolve by `(entity_type, code)` or `entity_id`.** Stocks: `entity_type='stock'` + 6-digit code (A-share) / ticker (US). Countries: `entity_type='country'` + ISO code.
- **`reorder` takes `entity_collection_items.id`**, not the entity id. Fetch item ids first.
- **Rule-based sync reverts manual adds** - the rule is authoritative. Tell the user before they hand-add to a rule-based collection.
- **`PRAGMA foreign_keys=ON`** is required for the FK to `entities` + cascade. `sqlite3` CLI enables it per-session if you prefix the command.
- **This skill does NOT define rules.** For a `rule_json`/`rule_script` collection from scratch, use `fd-daas-entities-collection-creator`.
