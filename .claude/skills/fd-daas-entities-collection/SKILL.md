---
name: fd-daas-entities-collection
description: Manage daas entities and entity collections day-to-day — discover entities (stocks/countries), list/view/create/delete collections, add/remove/reorder members, view the add-in/remove-out audit history, and re-sync rule-based collections. Use this skill whenever the user wants to operate on entities or collections WITHOUT defining a new rule — phrases like "list my collections", "show me the members of ...", "把 600519 加到 ... 集合", "remove AAPL from ...", "这个 collection 的历史变动", "sync 一下 ... collection", "daas 里有哪些股票/国家", "查一下比亚迪在哪个集合", "把这几个集合的成员重新排一下", or any entities/collections + "list / view / add / remove / members / history / sync / reorder / delete / 查 / 看 / 加 / 删 / 同步 / 排序". Make sure to use this skill for any entity or entity-collection operation that is NOT "define a new rule-based collection" (that is fd-daas-entities-collection-creator, which also handles Python rule scripts). Do NOT use this skill to define a script-based or rule_json-based membership rule from scratch (use the creator skill), or to build a dashboard (use fd-daas-dashboard-creator).
---

# fd-daas-entities-collection

Operate on entities and entity collections in daas.db — discover what's there, manage membership by hand, view history, and re-sync rule-based collections. This is the day-to-day operator skill; `fd-daas-entities-collection-creator` is the define-a-new-rule skill.

## Mental model

Match the user's intent to one of these, then run it. None of these *define* a rule — for that, hand off to `fd-daas-entities-collection-creator`.

- **Discover entities** → "what stocks do we have?" / "find BYD" → Step 1.
- **List / view collections** → "show my collections" / "who's in X?" → Step 2.
- **Create a manual or simple collection** → "make an empty watchlist" / "a collection of these 5 codes" → Step 3 (hand off to the creator skill if a rule/script is wanted).
- **Manage membership** → "add/remove/reorder members" → Step 4.
- **History** → "what changed in X?" → Step 5.
- **Sync** → "refresh X from its rule" → Step 6.
- **Delete** → "remove collection X" → Step 7.

## Step 1 — Discover entities

Goal: find an entity (stock or country) to operate on.

1. `mcp__daas-mcp__search_entities(query="<name/ticker/code>")` → matches case-insensitively against name, ticker, code, aliases. Returns `entity_id`, `code`, `name`, `entity_type` (`stock`/`country`), `exchange`, `country_code`.
2. For detail + linked datasources, `mcp__daas-mcp__get_entity(entity_id=<id>)` → aliases + the `links` list (datasources covering it). For "which datasources cover this entity and how do I fetch it", `mcp__daas-mcp__get_entity_coverage(entity_id=<id>)`.
3. To browse without a target, `mcp__daas-mcp__list_entities(entity_type="stock", exchange="SSE", limit=50)` — paginated; filter by `entity_type` / `exchange` / `country_code`.

**Not found**: tell the user "entity not found in daas", suggest a looser query (prefix/alias), and stop. Entities are seeded by `mcp/daas-mcp/entity_sync.py --sync-all` (5,530 stocks + 30 countries as of the last sync); if the user expects a stock that's missing, that's why.

## Step 2 — List / view collections

1. `mcp__daas-mcp__list_entity_collections()` → every collection with `id`, `name`, `description`, `rule` (the JSON object or null), `rule_script` (path or null), `item_count`, timestamps. Surface as a table.
2. `mcp__daas-mcp__get_entity_collection(name="<name>")` → `{name, description, rule, rule_script, members: [{code, name, entity_type, exchange, country_code, sort_order, added_at, added_reason}, …]}` ordered by `sort_order`. Show the member table.

**Reading via sql.js / sqlite3**: if daas-mcp isn't wired into `.mcp.json`, the dashboard reads collections directly via sql.js; for a quick CLI check, `sqlite3 mcp/daas.db "SELECT name, description, rule_script, (SELECT COUNT(*) FROM entity_collection_items i WHERE i.collection_id=c.id) AS n FROM entity_collections c"`.

## Step 3 — Create a manual or simple collection

For a **manual** collection (members added by hand later) or a **simple `rule_json`** collection (static attribute filter), create it here:

1. `mcp__daas-mcp__create_entity_collection(name="<name>", description="<desc>")` — manual collection (no rule). Add members by hand in Step 4.
2. `mcp__daas-mcp__create_entity_collection(name="<name>", description="<desc>", rule="<json string>")` — declarative rule (`entity_type`/`exchange`/`country_code`/`codes`/`name_regex`, AND-combined). Then Step 6 to populate.

**For a Python rule script** — hand off to `fd-daas-entities-collection-creator`. That skill authors the `members(ctx)` script, saves it to `mcp/daas-mcp/rules/entity_collections/<name>.py`, and creates the collection with `rule_script=<path>`. Don't try to inline a script here.

**Duplicate name**: returns `{"error": "Entity collection '<name>' already exists"}`. Offer to add members to the existing collection instead of recreating, or pick a new name.

## Step 4 — Manage membership (add / remove / reorder)

All of these resolve an entity by `entity_id`, or by `(entity_type, code)`:

1. **Add**: `mcp__daas-mcp__add_entity_to_collection(collection_name="<name>", code="<code>", entity_type="stock", reason="<why>")`. Records an `add_in` event (`source=manual`). No-op (`action: "already_member"`, no event) if already a member.
2. **Remove**: `mcp__daas-mcp__remove_entity_from_collection(collection_name="<name>", code="<code>", entity_type="stock", reason="<why>")`. Records a `remove_out` event (`source=manual`). No-op (`action: "not_member"`) if not a member.
3. **Reorder**: `mcp__daas-mcp__list_entity_collection_items(collection_name="<name>")` first to get each member's `id` (the `entity_collection_items.id`, not the entity id), then `mcp__daas-mcp__reorder_entity_collection_items(collection_name="<name>", ordered_item_ids=[<item.id>, …])` — must contain exactly the current item ids, no duplicates.
4. **List**: `mcp__daas-mcp__list_entity_collection_items(collection_name="<name>")` → the current ordered member set.

For a bulk add (e.g. "add these 20 codes"), loop `add_entity_to_collection` — already-members are no-ops, so re-running is safe.

## Step 5 — View the audit history

`mcp__daas-mcp__list_entity_collection_changes(collection_name="<name>"?, entity_id=<id>?, action="add_in"|"remove_out"?, source="manual"|"cron"?, limit=100, offset=0)` → newest-first, each row enriched with `collection_name` + `entity_code` + `entity_name` + `action` + `source` + `reason` + `changed_at`.

- `source=manual` = a hand add/remove (Step 4); `source=cron` = a rule-driven sync (Step 6) recorded the transition.
- Filter by `entity_id` to trace one entity across all collections; by `action` to see only joins or only exits.

**Reading via sqlite3**: `sqlite3 mcp/daas.db "SELECT changed_at, action, source, reason, entity_id FROM entity_collection_changes WHERE collection_id=(SELECT id FROM entity_collections WHERE name='<name>') ORDER BY changed_at DESC LIMIT 20"`.

## Step 6 — Sync a rule-based collection

`mcp__daas-mcp__sync_entity_collection(name="<name>")` → re-derives the member set from the collection's rule (`rule_json` filter OR `rule_script` execution), diffs vs current, applies add_in / remove_out (`source=cron`), returns `{action: "synced", rule: "json"|"script", added: [..], removed: [..], unchanged: N}`.

- **Manual collection** (no rule) → returns `{action: "manual_collection", unchanged: N}` — a no-op. Tell the user "this is a manual collection; add/remove members by hand instead".
- **Script rule** → the runner loads the path in `rule_script`, calls `members(ctx)`, and diffs. If the script is missing, returns a `FileNotFoundError`; tell the user the stored path no longer exists and offer to re-point it (`update_entity_collection(rule_script="<new path>")`) or clear it (`clear_rule=true`).
- **Ad-hoc / dry-run**: `uv run --directory mcp/daas-mcp python entity_collection_sync.py --sync <name> --dry-run` reports `rule_kind`, the rule/script path, `current_members`, `intended_members` — useful before applying a diff.

## Step 7 — Delete

`mcp__daas-mcp__delete_entity_collection(name="<name>")` — cascades to `entity_collection_items` + `entity_collection_changes` (real FKs, `ON DELETE CASCADE`). Confirm with the user first — deletion is irreversible and removes the audit history too. Deleting the collection does **not** delete the rule script file on disk (if `rule_script` was set); offer to remove it (`rm mcp/daas-mcp/rules/entity_collections/<name>.py`) and unregister any cron (`entity_collection_sync.py --unregister-cron <name>`).

## Gotchas

- **`add`/`remove` resolve by `(entity_type, code)` or `entity_id`.** For stocks, `entity_type="stock"` + the 6-digit code (A-share) / ticker (US). For countries, `entity_type="country"` + the ISO code. If the entity isn't found, the tool returns a clear error — don't guess the type.
- **`reorder` takes `entity_collection_items.id` (the membership row id), not the entity id.** Fetch `list_entity_collection_items` first and use its `id` field; the set must match exactly or the call is rejected.
- **`source=cron` vs `source=manual` in history.** Rule-driven syncs record `cron` even on ad-hoc runs — that's by design (it marks rule-driven transitions). Only hand add/remove records `manual`. Don't "fix" a `cron` row by re-adding manually.
- **Syncing a rule-based collection reverts manual adds — the rule is authoritative.** A rule (json or script) defines the *full* intended set; `sync_entity_collection` diffs that set against current members and remove_out's anything not in it — including members added by hand. If a user hand-adds a stock to a rule-based collection, the next sync will drop it. Tell the user this before they hand-add to a rule-based collection. If they want a mix of rule + manual members, the clean options are: (a) edit the rule to include the extra codes, (b) keep a separate manual collection, or (c) clear the rule (`update_entity_collection(clear_rule=true)`) and manage purely by hand.
- **Syncing a manual collection is a no-op**, not an error. If the user expects a sync to do something, the collection has no rule — either add members by hand (Step 4) or define a rule via the creator skill.
- **Deletion cascades to items + changes** but not to the rule script file or the cron schedule. Clean those up explicitly (Step 7).
- **This skill does NOT define rules.** For a `rule_json` or `rule_script` collection created from scratch, use `fd-daas-entities-collection-creator`. This skill creates only manual or simple-`rule_json` collections (Step 3) and operates on existing ones.
- **For the full entity → datasource → indicator flow**, use `fd-daas-fetch-data`. This skill's entity discovery (Step 1) is just enough to find an entity to add to a collection.
