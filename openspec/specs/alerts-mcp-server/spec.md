### Requirement: FastMCP alerts-mcp server with stdio transport

The system SHALL provide a FastMCP server at `mcp/alerts-mcp/server.py` using stdio transport, registered in root `.mcp.json` via `uv run --directory mcp/alerts-mcp python server.py`, following the same layout conventions as `process-mcp` and `edgartools-mcp`. The server SHALL load dotenv from root `.env` first, then its own per-MCP `.env` with `override=True`, and SHALL read its database URL from `DAAS_DATABASE_URL`.

#### Scenario: Server starts and registers tools

- **WHEN** the server is started with `python3 server.py`
- **THEN** it runs FastMCP with `transport="stdio"` and `show_banner=False`, and all alert tools are registered and callable over stdio

#### Scenario: Registered in .mcp.json

- **WHEN** root `.mcp.json` is inspected
- **THEN** it contains an `alerts-mcp` entry with `type: stdio` and a `uv run --directory ... python server.py` command, parallel to the `process-mcp` entry

### Requirement: Two new tables via Base.metadata.create_all with FK cascade

The system SHALL add `AlertRule` and `AlertEvent` models to the shared `mcp/models/` package. Tables `alert_rules` and `alert_events` SHALL be created in `mcp/daas.db` via `DAAS_DATABASE_URL` using `Base.metadata.create_all` (no Alembic). `alert_events.rule_id` SHALL be a real foreign key to `alert_rules.id` with `ON DELETE CASCADE`. The server SHALL set `PRAGMA foreign_keys=ON` per-connection so deleting a rule drops its event history.

#### Scenario: Tables created on first start

- **WHEN** the server starts against a `daas.db` that lacks the tables
- **THEN** `alert_rules` and `alert_events` are created, and existing tables are untouched

#### Scenario: Deleting a rule cascades to its events

- **WHEN** a rule with existing `alert_events` rows is deleted
- **THEN** all of that rule's `alert_events` rows are also deleted by the cascade

### Requirement: Alert-scoped data inspection tools

The server SHALL expose `list_series` and `get_series_latest` tools that read `mcp/daas.db` for the purpose of building trigger rules (these are NOT a general SQL browser — `dashboard-mcp.query_table` owns that). `list_series` SHALL return the distinct `(source, function_name, indicator)` triples present in the `observations` table plus any `scraw_*` tables (excluding `scraw_configs`), each with a row count and latest date. `get_series_latest(source_table, series_filter_json, date_column, value_column, limit)` SHALL return the latest `limit` rows of a series ordered by `date_column` desc. All table/column identifiers SHALL be validated against `^[A-Za-z_][A-Za-z0-9_]*$` and never interpolated as raw SQL.

#### Scenario: list_series over observations

- **WHEN** `list_series()` is called and `observations` contains rows
- **THEN** it returns distinct `(source, function_name, indicator)` triples with row counts

#### Scenario: get_series_latest returns newest rows

- **WHEN** `get_series_latest(source_table="observations", series_filter_json={"indicator":"rsi"}, date_column="date", value_column="value", limit=5)` is called
- **THEN** it returns at most 5 rows ordered by `date` descending

#### Scenario: Invalid identifier is rejected

- **WHEN** a tool is called with `value_column="value; DROP TABLE"`
- **THEN** it returns an `error` without executing the SQL, because the identifier fails the `^[A-Za-z_][A-Za-z0-9_]*$` guard

### Requirement: Alert rule CRUD

The server SHALL expose `create_alert_rule`, `list_alert_rules`, `get_alert_rule`, `update_alert_rule`, and `delete_alert_rule` tools. A rule SHALL persist: `name` (unique), `enabled`, `source_table` (default `observations`), `series_filter_json`, `date_column`, `value_column`, `condition` (DSL string), `fire_mode` (`every_match` or `on_change`), `cooldown_seconds`, `channels_json` (list of channel names, optionally with per-rule overrides like `{"telegram": {"chat_id": "…"}}`), `message_template`, and runtime state `last_state` / `last_fired_at` / `last_value`. `create_alert_rule` SHALL validate that `source_table` exists in `sqlite_master` and the named columns exist via `PRAGMA table_info` before persisting.

#### Scenario: Create a rule

- **WHEN** `create_alert_rule(name="rsi-overbought", condition="latest > 70", channels_json=["telegram"], message_template="RSI($latest) on $indicator is overbought")` is called
- **THEN** a rule row is persisted with `enabled=True`, `fire_mode="every_match"` default, and `last_state=NULL`

#### Scenario: Duplicate name rejected

- **WHEN** `create_alert_rule` is called with a `name` that already exists
- **THEN** it returns an `error` and does not create a duplicate

#### Scenario: Create rejects a non-existent source table

- **WHEN** `create_alert_rule` is called with `source_table="does_not_exist"`
- **THEN** it returns an `error` indicating the table was not found in `sqlite_master`, and no rule is persisted

### Requirement: Safe condition DSL via whitelisted ast walk

The server SHALL evaluate a rule's `condition` using `expressions.evaluate(expr, ctx)` which compiles with `ast.parse(expr, mode="eval")` and walks the tree allowing only `BoolOp`, `UnaryOp`, `Compare`, `BinOp`, `Name`, `Constant`, and `Call` nodes — where `Call` is restricted to a fixed whitelist (`crosses_above`, `crosses_below`, `pct_change`, `value`, `avg`, `min`, `max`) and `Name` resolves only to `latest` or `prev`. The evaluator SHALL reject any expression containing `Attribute`, `Subscript`, comprehensions, unknown names, or un-whitelisted calls by raising `ExpressionError`. The evaluator SHALL NOT use `eval` or `exec`.

#### Scenario: Threshold condition evaluates true

- **WHEN** `expressions.evaluate("latest > 70", {"latest": 75.0, "prev": 68.0})` is called
- **THEN** it returns `True`

#### Scenario: crosses_above detects a transition

- **WHEN** `expressions.evaluate("crosses_above(70)", {"latest": 72.0, "prev": 68.0})` is called
- **THEN** it returns `True` (prev ≤ 70 and latest > 70)

#### Scenario: Malicious expression is rejected

- **WHEN** `expressions.evaluate("__import__('os').system('rm -rf /')", {})` is called
- **THEN** it raises `ExpressionError` without executing any code

#### Scenario: Attribute access is rejected

- **WHEN** `expressions.evaluate("latest.__class__", {"latest": 1})` is called
- **THEN** it raises `ExpressionError`

### Requirement: Fire modes and cooldown

The rule engine SHALL support `fire_mode` of `every_match` (fire on every true evaluation subject to cooldown) and `on_change` (fire only on a false→true transition). `cooldown_seconds` SHALL gate dispatch by comparing the current time to `last_fired_at` on the rule row. `on_change` SHALL persist `last_state` (bool) between cron ticks so a `cron-mcp` restart resumes correctly. A false evaluation SHALL set `last_state=False` without dispatching.

#### Scenario: on_change fires only on transition

- **WHEN** a rule with `fire_mode="on_change"` and `last_state=False` evaluates true
- **THEN** a notification is dispatched, `last_fired_at` is updated, and `last_state` is set to `True`

#### Scenario: on_change does not refire while staying true

- **WHEN** the same rule evaluates true again on the next tick (`last_state` already `True`)
- **THEN** no notification is dispatched

#### Scenario: cooldown gates every_match

- **WHEN** a rule with `fire_mode="every_match"`, `cooldown_seconds=300` last fired 100 seconds ago evaluates true
- **THEN** no notification is dispatched because the cooldown window has not elapsed

### Requirement: Pluggable notifier with seven channel adapters

The server SHALL define a `Notifier` abstract base class with `name`, `is_configured() -> bool`, and `send(message, ctx) -> dict`, and a registry that maps channel names to adapter instances. Seven adapters SHALL be shipped: `telegram`, `discord`, `slack`, `twitter`, `dingtalk`, `feishu`, `wecowork` (企业微信). Each adapter SHALL read its credentials from root `.env` (loaded per the standard dotenv order) under `ALERTS_*` prefixes. When a rule fires, the dispatcher SHALL fan out to every channel listed in the rule's `channels_json`, collect each result into `channels_results_json`, and not abort the whole dispatch if one channel fails.

#### Scenario: All seven adapters are registered

- **WHEN** the server starts
- **THEN** the registry contains adapters named `telegram`, `discord`, `slack`, `twitter`, `dingtalk`, `feishu`, and `wecowork`

#### Scenario: Unconfigured channel is recorded, not raised

- **WHEN** a rule lists `["telegram", "slack"]` and Slack's webhook URL is unset
- **THEN** Telegram sends successfully and Slack's entry in `channels_results_json` is `{"ok": false, "error": "not configured"}`

#### Scenario: Per-rule channel override falls back to env default

- **WHEN** a rule's `channels_json` is `{"telegram": {"chat_id": "123"}}` and `ALERTS_TELEGRAM_CHAT_ID` is also set
- **THEN** the message is sent to chat `123` (per-rule override wins), and a rule without the override uses the env default

### Requirement: Social credentials managed in .env

All channel credentials SHALL be read from root `.env` under `ALERTS_*` prefixes: `ALERTS_TELEGRAM_BOT_TOKEN`, `ALERTS_TELEGRAM_CHAT_ID`, `ALERTS_DISCORD_WEBHOOK_URL`, `ALERTS_SLACK_WEBHOOK_URL`, `ALERTS_DINGTALK_WEBHOOK_URL`, `ALERTS_DINGTALK_SECRET`, `ALERTS_FEISHU_WEBHOOK_URL`, `ALERTS_FEISHU_SECRET`, `ALERTS_WECOM_WEBHOOK_URL`, `ALERTS_WECOM_SECRET`, `ALERTS_TWITTER_CONSUMER_KEY`, `ALERTS_TWITTER_CONSUMER_SECRET`, `ALERTS_TWITTER_ACCESS_TOKEN`, `ALERTS_TWITTER_ACCESS_TOKEN_SECRET`. The server SHALL NOT require any channel to be configured — an unconfigured channel reports `is_configured()=False`.

#### Scenario: No channel keys is not fatal

- **WHEN** the server starts with no `ALERTS_*` env vars set
- **THEN** the server starts successfully and every adapter reports `is_configured()=False`

### Requirement: list_channels reports configuration without leaking secrets

The server SHALL expose a `list_channels` tool that returns, for each of the seven channels, `{name, configured: bool, missing_keys: [names]}`. The tool SHALL NEVER return credential values — only the names of missing keys. The Twitter adapter's OAuth signing helper SHALL be the only consumer of the Twitter secrets.

#### Scenario: list_channels redacts secrets

- **WHEN** `list_channels()` is called after `ALERTS_TELEGRAM_BOT_TOKEN="secret"` is set
- **THEN** the `telegram` entry shows `configured=true` and the response body contains no occurrence of the string `secret`

### Requirement: Message rendering via string.Template

The server SHALL render message bodies with `string.Template(message_template).safe_substitute(...)`, exposing at least `$latest`, `$prev`, `$date`, `$rule_name`, `$source`, `$indicator`, `$value`, and `$pct_change`. `safe_substitute` SHALL leave unknown placeholders intact rather than raising. The renderer SHALL NOT use `str.format` (which permits attribute access).

#### Scenario: Template substitutes values

- **WHEN** a rule with `message_template="$rule_name: $indicator is $latest"` fires with `latest=75.0`
- **THEN** the rendered message is `"<rule_name>: <indicator> is 75.0"`

#### Scenario: Unknown placeholder left intact

- **WHEN** a template contains `$unknown` and no `unknown` variable is provided
- **THEN** the rendered message leaves `$unknown` in place rather than raising

### Requirement: alert_events logging per dispatch

Each time a rule fires, the server SHALL insert one row into `alert_events` with `rule_id`, `fired_at`, `value_json` (the series values that triggered), `message_rendered`, and `channels_results_json` (per-channel `{ok, error?}`). Rules that evaluate false SHALL NOT create an event row. The engine SHALL update `last_fired_at`, `last_state`, and `last_value` on the rule row in the same transaction as the event insert.

#### Scenario: Firing records an event

- **WHEN** a rule evaluates true and dispatches
- **THEN** one `alert_events` row is inserted with `channels_results_json` reflecting each channel's outcome, and the rule's `last_fired_at` and `last_state` are updated in the same transaction

#### Scenario: False evaluation records no event

- **WHEN** a rule evaluates false
- **THEN** no `alert_events` row is inserted (only `last_state` is updated)

### Requirement: Cron CLI branches --run-rule and --run-all

The server SHALL support `python server.py --run-rule <name>` (evaluate and dispatch one rule, then exit) and `python server.py --run-all` (evaluate every enabled rule once, then exit), each printing a JSON summary to stdout. These branches SHALL NOT start the stdio MCP server. `--run-all` SHALL be sequential with per-rule try/except so one rule's failure does not stop the rest. The cron task command for `cron-mcp` SHALL be `uv run --directory /Users/chengsishi/code/cli-anything/mcp/alerts-mcp python server.py --run-rule <name>`.

#### Scenario: --run-rule evaluates and exits

- **WHEN** `python server.py --run-rule rsi-overbought` is run and the rule's condition is true
- **THEN** notifications are dispatched, a JSON summary is printed, and the process exits without starting the stdio server

#### Scenario: --run-all continues past a failed rule

- **WHEN** `--run-all` runs and one rule raises during evaluation
- **THEN** that rule is reported as failed in the JSON summary and the remaining rules still run

### Requirement: Offline self-check with temp DB and stub notifiers

The server SHALL ship `selfcheck.py` that creates a temp DB (no `daas.db` mutation), stubs every notifier adapter so no network call and no real social post occurs, and exercises: rule CRUD, condition evaluator (including malicious-expression rejection), the `on_change` false→true→false→true cycle, cooldown gating, dispatch fan-out with a failing channel, event-row insertion, and a `list_channels` secret-redaction assertion. The self-check SHALL pass with no `ALERTS_*` env vars set.

#### Scenario: Self-check passes with no env and no network

- **WHEN** `uv run --directory mcp/alerts-mcp python selfcheck.py` is run
- **THEN** it creates a temp DB, runs every exercise against stubbed notifiers, makes zero network calls, and exits 0

#### Scenario: Self-check asserts no secret leakage

- **WHEN** the self-check runs `list_channels` after injecting a known secret into the environment
- **THEN** it asserts the secret string does not appear anywhere in the `list_channels` output
