## 1. Shared schema package

- [x] 1.1 Add `AlertRule` and `AlertEvent` SQLAlchemy models to `mcp/models/` on the shared `Base`: `alert_rules` (id, name UNIQUE, enabled, source_table, series_filter_json, date_column, value_column, condition, fire_mode, cooldown_seconds, channels_json, message_template, last_state, last_fired_at, last_value, created_at, updated_at) and `alert_events` (id, rule_id FK→alert_rules.id ON DELETE CASCADE, fired_at, value_json, message_rendered, channels_results_json, created_at). Re-export from `mcp/models/__init__.py`.
- [x] 1.2 Verify in a temp SQLite DB that `Base.metadata.create_all` creates both tables and that `PRAGMA foreign_keys=ON` makes deleting a rule cascade to its `alert_events`.

## 2. Database layer (`alert_database.py`)

- [x] 2.1 Implement the `Database` singleton mirroring `process_database.py`: connect via `DAAS_DATABASE_URL`, resolve relative URLs against the repo root (so `--run-rule` works under `uv run --directory`), set `PRAGMA foreign_keys=ON`, run `Base.metadata.create_all`.
- [x] 2.2 Implement the identifier guard: validate `source_table`, `date_column`, `value_column`, and every key in `series_filter_json` against `^[A-Za-z_][A-Za-z0-9_]*$`; raise on invalid (reuse the `process_database.py` pattern). Filter values are passed as bind params, never interpolated.
- [x] 2.3 Implement `list_series()` (distinct `(source, function_name, indicator)` from `observations` + `scraw_*` tables excluding `scraw_configs`, each with row count + latest date) and `get_series_latest(source_table, series_filter_json, date_column, value_column, limit)` ordered by `date_column` desc, WHERE built from bind params.
- [x] 2.4 Implement rule CRUD (`create`/`list`/`get`/`update`/`delete`): `create` validates `source_table` exists in `sqlite_master` and `date_column`/`value_column` exist via `PRAGMA table_info` before persisting; `create` rejects duplicate `name`; `delete` relies on the FK cascade.
- [x] 2.5 Implement `record_firing(rule_id, value_json, message_rendered, channels_results_json)` inserting an `alert_events` row and updating `last_fired_at`/`last_state`/`last_value` on the rule in one transaction.

## 3. Condition DSL (`expressions.py`)

- [x] 3.1 Implement `evaluate(expr, ctx) -> bool` via `ast.parse(expr, mode="eval")` + recursive walk allowing only `BoolOp`, `UnaryOp`, `Compare`, `BinOp`, `Name`, `Constant`, `Call`.
- [x] 3.2 Implement the whitelisted functions, `crosses_below(t)`, `pct_change(n)`, `value(n)`, `avg(n)`, `min(n)`, `max(n)` operating on `ctx["series"]` (recent values, newest first) and `ctx["latest"]`/`ctx["prev"]`.
- [x] 3.3 Reject `Attribute`, `Subscript`, comprehensions, unknown names, and un-whitelisted calls by raising `ExpressionError`. Confirm `eval`/`exec` are never invoked.
- [x] 3.4 Add assertions to the self-check for: threshold true/false, `crosses_above` true/false, `pct_change(5) > 0.05`, and malicious expressions (`__import__('os').system('rm -rf /')`, `latest.__class__`, `().__class__.__bases__`) all raising `ExpressionError`.

## 4. Notifier plugin layer (`notifiers/`)

- [x] 4.1 Implement `Notifier` ABC (`name`, `is_configured() -> bool`, `send(message, ctx) -> dict`) and `registry.py` mapping channel names → adapter instances; `registry.send(channel, message, ctx)` returns `{ok: False, error: "not configured"}` for missing/unconfigured channels instead of raising.
- [x] 4.2 Implement `telegram.py` (POST `/sendMessage` with `bot_token` + `chat_id`; per-rule override via `channels_json["telegram"]["chat_id"]` else `ALERTS_TELEGRAM_CHAT_ID`) using `httpx`.
- [x] 4.3 Implement `discord.py` and `slack.py` (single POST to the webhook URL).
- [x] 4.4 Implement `dingtalk.py`, `feishu.py`, `wecowork.py` (企业微信) webhook adapters, each with optional HMAC-SHA256 secret signing (DingTalk `&timestamp=`, Feishu `X-Lark-Signature`, WeCom per its webhook-sign docs).
- [x] 4.5 Implement `twitter.py` via OAuth 1.0a HMAC-SHA1 signing hand-rolled over stdlib `hmac`/`hashlib`/`urllib.parse`, POSTing `statuses/update` with the four `ALERTS_TWITTER_*` secrets.
- [x] 4.6 Add a Twitter signing assertion to the self-check against a known RFC 5849 test vector.
- [x] 4.7 Implement `list_channels()` returning `{name, configured, missing_keys}` for all seven adapters, never returning credential values.

## 5. Message rendering

- [x] 5.1 Implement `render_message(template, ctx)` using `string.Template(template).safe_substitute(latest, prev, date, rule_name, source, indicator, value, pct_change)`; confirm `str.format` is not used.

## 6. Rule engine (`engine.py`)

- [x] 6.1 Implement `evaluate_rule(rule)` — load enough recent values for the largest window referenced by the condition, build the DSL ctx, run `expressions.evaluate`.
- [x] 6.2 Implement fire logic: `on_change` fires only on a false→true transition (using `last_state`); `every_match` fires every true evaluation subject to `cooldown_seconds` vs `last_fired_at`. A false evaluation sets `last_state=False` and inserts no event.
- [x] 6.3 Implement dispatch: render the message, fan out to every channel in `channels_json` via `registry.send`, collect `channels_results_json`, then `record_firing` (event row + rule-state update) in one transaction.
- [x] 6.4 Confirm one channel's failure does not abort the dispatch (try/except per channel).

## 7. MCP tools + server (`alert_tools.py`, `server.py`)

- [x] 7.1 Expose `list_series`, `get_series_latest`, `create_alert_rule`, `list_alert_rules`, `get_alert_rule`, `update_alert_rule`, `delete_alert_rule`, `list_channels`, and `run_rule` (ad-hoc evaluate-and-dispatch one rule now).
- [x] 7.2 Wire the FastMCP server in `server.py`: dotenv load (root `.env` first, own `.env` with `override=True`), `transport="stdio"`, `show_banner=False`, `Base.metadata.create_all` on start.
- [x] 7.3 Add CLI branches `--run-rule <name>` and `--run-all` (sequential, per-rule try/except, JSON summary to stdout, no stdio server start).

## 8. Packaging, registration, env

- [x] 8.1 Create `mcp/alerts-mcp/pyproject.toml` (`fastmcp>=2.0`, `httpx`, `python-dotenv>=1.0`, `sqlalchemy>=2.0`, `mcp-models`, `requires-python>=3.10`).
- [x] 8.2 Add `alerts-mcp` to root `.mcp.json` (`uv run --directory mcp/alerts-mcp python server.py`, stdio), parallel to the `process-mcp` entry.
- [x] 8.3 Add `mcp/alerts-mcp/.env.example` documenting all `ALERTS_*` keys; confirm the server starts with zero `ALERTS_*` vars set.

## 9. Self-check (`selfcheck.py`)

- [x] 9.1 Create a temp DB, stub every notifier (no network, no real posts), and run: rule CRUD → condition eval incl. malicious-expression rejection → `on_change` false→true→false→true cycle → cooldown gating → dispatch with one failing channel → event-row insertion → `list_channels` secret-redaction assertion. Exits 0 with no `ALERTS_*` env set.
- [x] 9.2 Run `uv run --directory mcp/alerts-mcp python selfcheck.py` and confirm it passes against a clean temp DB without touching `mcp/daas.db`.

## 10. Docs

- [x] 10.1 Add an `mcp/alerts-mcp/` subsection to root `CLAUDE.md` (entry, database, models, key files, channels + `ALERTS_*` env vars, self-check, cron CLI branches) matching the sibling-MCP format.
- [x] 10.2 If `specs/001-daas-provider/plan.md` or any project-level doc enumerates the MCP inventory, add `alerts-mcp` to it.
