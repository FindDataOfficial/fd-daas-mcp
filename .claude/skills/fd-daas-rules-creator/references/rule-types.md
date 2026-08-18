# Rule types contract

A rule is a row in the `rules` table: `name` (UNIQUE), `rule_type` ∈ {`json`, `script`, `position`, `llm`}, `target` ∈ {`entity_ids`, `indicator_names`, `rows`}, `config_json` (a JSON object whose shape is dictated by `rule_type`), `description`, `enabled`. The `RuleEngine` (`fd-daas-mcp/daas-mcp/rule_engine.py`) dispatches on `rule_type`.

`target` is what the rule yields:
- `entity_ids` - the rule returns entity ids (drives an entity collection). Member items are normalized: `str` -> stock code (entity_type defaults to `stock`), `{"entity_type":..,"code":..}`, `{"entity_id":int}`, or `int`.
- `indicator_names` - the rule returns indicator rule names (drives an indicator collection).
- `rows` - the rule extracts row records into `process_results` (llm only; via `daas_run_rule`).

## `json` - declarative entity filter

`config_json` keys (all optional, AND-combined): `entity_type`, `exchange`, `country_code`, `codes` (list), `name_regex`. `target` MUST be `entity_ids`. `name_regex` uses Python `re.search` (a `REGEXP` function is registered on the daas engine).

```json
{"entity_type": "stock", "exchange": "SSE", "name_regex": "银行$"}
```

## `script` - Python `members(ctx)`

`config_json`: `{"script_path": "<repo-root-relative or absolute>", "function": "members"}` (default `function='members'`). The script runs with a read-only `RuleContext`:

```python
def members(ctx):
    # ctx.query(sql, params=()) -> list[dict]   (read-only; mode=ro)
    # ctx.http_get(url, headers=None, timeout=30) -> str
    # ctx.llm(prompt, text, schema=None, model=None) -> dict|list
    rows = ctx.query("SELECT symbol AS code FROM scraw_us_top300_screen WHERE in_pool_a=1")
    return [r["code"] for r in rows]
```

Returned items (for `target='entity_ids'`) may be: `str` (stock code), `{"entity_type":..,"code":..}`, `{"entity_id":int}`, or `int`. Unknown items are skipped (not fatal). Return the **full intended set** every run - the sync diffs. For `target='indicator_names'` return strings (indicator names); for `target='rows'` return dicts.

Save the script to a repo-root-relative path, e.g. `rules/entity_collections/<name>.py`. The DB connection is `mode=ro` - a write raises `sqlite3.OperationalError`.

## `position` - structural extraction (CSS / xpath / regex / jsonpath)

`config_json`:
```json
{
  "source": {"type": "url|file|text|table", "value": "..."},
  "selector_type": "css|xpath|regex|jsonpath",
  "selector": "...",
  "extract": "text|@<attr>"
}
```
- `source.type`:
  - `text` - `value` is the inline text.
  - `url` - `value` is fetched via httpx (`ctx.http_get`).
  - `file` - `value` is a repo-root-relative or absolute path (UTF-8).
  - `table` - `value` is `{"table": "<scraw_*>", "column": "<text col>"}`; all rows' column text is joined.
- `selector_type`:
  - `regex` - stdlib `re`; if the pattern has a capture group, group 1 is taken, else the full match.
  - `css` / `xpath` - `lxml` (+ `cssselect`); `extract: "text"` -> node text, `"@href"` -> the `href` attribute.
  - `jsonpath` - `jsonpath-ng` against JSON-parsed text.
- Returns the extracted strings; for `target='entity_ids'` they're resolved to entity ids (e.g. stock codes).

```json
{
  "source": {"type": "url", "value": "https://example.com/holdings"},
  "selector_type": "css",
  "selector": "table.holdings td.code",
  "extract": "text"
}
```

Requires `lxml`+`cssselect` (css/xpath) and `jsonpath-ng` (jsonpath); `regex` needs no extra dep. A missing dep returns a clear error, not a crash.

## `llm` - natural-language extraction

Two modes:

**Member mapping** (`target='entity_ids'` / `'indicator_names'`): extract from inline `text`, map records to members.
```json
{
  "text": "<the document text>",
  "schema_json": {"type": "object", "properties": {"code": {"type": "string"}}},
  "prompt": "Extract every 6-digit A-share stock code mentioned.",
  "model": "default",
  "max_chars": 12000,
  "mapping": {"code_from": "code"}
}
```
`mapping`: for `entity_ids`, `code_from` (default `code`) selects the record field holding the stock code; for `indicator_names`, `name_from` (default `name`). Reuses `process_tools.extract_text` (chunking + JSON-Schema validation + retry).

**Row extraction** (`target='rows'`): incremental over a source table, written to `process_results` by `daas_run_rule`.
```json
{
  "source_table": "scraw_news_finance",
  "text_column": "body",
  "schema_json": {"type": "object", "properties": {"ticker": {"type": "string"}, "sentiment": {"type": "string"}}},
  "prompt": "Extract the ticker and sentiment from each news row.",
  "model": "default",
  "max_chars": 12000,
  "last_rowid": 0
}
```
`daas_run_rule(name, batch=500)` reads rows with `rowid > config_json.last_rowid`, extracts each, upserts into `process_results` on `(rule_id, source_table, source_rowid)`, and advances `last_rowid`. `source_table`/`text_column` are validated against `^[A-Za-z_][A-Za-z0-9_]*$` + existence before any query.

Requires LLM env: `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` (single default model) or `PROCESS_MODELS` (named registry). Unconfigured -> `{"error":...}` without a network call.

## Tools (fd-daas-mcp CLI)

```
daas create_rule    name=<n> rule_type=<t> target=<t> config_json='<json>' [description=..] [enabled=true]
daas list_rules     [rule_type=<t>]
daas get_rule       name=<n>
daas update_rule    name=<n> [rule_type=..] [target=..] [config_json=..] [description=..] [enabled=..]
daas delete_rule    name=<n>          # nulls referencing collections' rule_id; cascades process_results
daas test_rule      name=<n> [limit=N] # dry-run (no persist)
daas run_rule       name=<n> [batch=500]  # persist: rows->process_results; members->returns the set
daas sync_entity_collection      name=<coll>
daas sync_indicator_collection   name=<coll>
```

Invoke via `fd-daas-mcp/.venv/bin/python -m daas.fd_daas_mcp.cli daas <tool> name=... --json`.

## Debugging an empty result

- `json`: run the filter directly - `sqlite3 daas.db "SELECT id,code,name FROM entities WHERE <filter>"`.
- `script`: run the script's `members()` query against `sqlite3` to see what it returns.
- `position`: test the selector against the fetched source (`curl`/read the URL/file, apply the regex/CSS).
- `llm`: call `daas extract_text text='<sample>' schema='<json>' --json` to see what the model returns before wiring the rule.
