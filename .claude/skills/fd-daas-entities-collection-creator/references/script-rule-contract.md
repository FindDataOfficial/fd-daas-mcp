# Script-rule contract

A `rule_script` is a Python file defining a top-level `members(ctx)` that returns the intended member set of an entity collection. `sync_entity_collection` loads the script, calls `members(ctx)`, diffs the result against the current members, and records add_in / remove_out in `entity_collection_changes`.

## `members(ctx)` signature

```python
def members(ctx):
    # ctx.query(sql: str, params=()) -> list[dict]
    #   Runs a SELECT against daas.db (read-only — SQLite mode=ro).
    #   Each row is a dict keyed by column name. params may be a tuple/list
    #   (positional) or a dict (named).
    ...
    return [...]   # the intended member set (full set, not a delta)
```

## Return-item forms

Each item in the returned list may be:

| form | meaning |
|---|---|
| `str` | a stock code (entity_type defaults to `stock`) — the common case |
| `{"entity_type": "stock", "code": "600519"}` | a stock by code, explicit type |
| `{"entity_type": "country", "code": "CN"}` | a country by code |
| `{"entity_id": 123}` | an entity by its internal id |
| `int` | an entity id directly |

Items that don't resolve to a known entity are **skipped** (not fatal). The runner resolves codes via `SELECT … FROM entities WHERE entity_type=? AND code=?`.

Return the **full intended set** on every run. The sync computes the diff itself.

## What `ctx.query` can read

Any table in daas.db — `entities`, `observations`, `entity_datasource_links`, `entity_collection_items` (another collection's current members), and any `scraw_*` snapshot table (e.g. `scraw_stock_zh_a_hist`, `scraw_dzjy`). Use `sqlite3 daas.db ".tables"` to discover what's available, and `PRAGMA table_info(<table>)` for columns.

The connection is read-only by construction (`mode=ro`); a write or DDL statement raises `sqlite3.OperationalError`. Don't try to persist anything from the script.

## Examples

### A. Static filter that rule_json could also express (str codes)

```python
def members(ctx):
    rows = ctx.query(
        "SELECT code FROM entities "
        "WHERE entity_type='stock' AND exchange='SSE' ORDER BY code"
    )
    return [r["code"] for r in rows]
```

### B. Cross-table: stocks in today's block-trade table

```python
def members(ctx):
    rows = ctx.query(
        "SELECT DISTINCT symbol AS code FROM scraw_dzjy "
        "WHERE amount > 10000000 ORDER BY code"
    )
    return [r["code"] for r in rows]
```

### C. Observation-driven: stocks whose latest close crossed a threshold

```python
def members(ctx):
    rows = ctx.query(
        "SELECT entity_code AS code FROM observations "
        "WHERE indicator='close' AND value > 100 "
        "GROUP BY entity_code ORDER BY entity_code"
    )
    return [r["code"] for r in rows]
```

(Adapt the column names to your actual `observations` schema — check with `PRAGMA table_info(observations)`.)

### D. Union of two other collections

```python
def members(ctx):
    rows = ctx.query(
        "SELECT DISTINCT e.code "
        "FROM entity_collection_items i "
        "JOIN entity_collections c ON c.id = i.collection_id "
        "JOIN entities e ON e.id = i.entity_id "
        "WHERE c.name IN ('momentum', 'value') AND e.entity_type='stock'"
    )
    return [r["code"] for r in rows]
```

### E. Mixed return forms (str + dict + entity_id)

```python
def members(ctx):
    return [
        "600519",                                   # str → stock
        {"entity_type": "stock", "code": "600036"}, # dict → stock
        {"entity_id": 42},                          # dict → entity_id
    ]
```

## Where to save the script

`rules/entity_collections/<collection_name>.py` — repo-root-relative, version-controlled (it's an authored rule, not generated data). The Write tool creates the parent dir. Pass the **repo-root-relative** path to `create_entity_collection(rule_script=…)`:

```
rules/entity_collections/<collection_name>.py
```

## How to debug a script that matched zero entities

```bash
# 1. Run the script's own query against the DB to see what it would return:
sqlite3 daas.db "SELECT code FROM entities WHERE exchange='SSE'"

# 2. Edit the script, re-sync via the fd-daas-mcp CLI:
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli daas sync_entity_collection name=<name> --json
```

The standalone `entity_collection_sync.py --sync <name> --dry-run` can print a plan (rule_kind, rule_script path, intended_members) but currently can't run outside the server (a `models`-import limitation), so the CLI sync above is the working path and the query in step 1 is your dry-run. `intended_members` is the count the script returned (after unknown-code skipping); `current_members` is what's in the collection now. If `intended_members` is null, the collection has no rule (manual).
