## Context

The project's data pipeline currently terminates in `mcp/daas.db`: `process-mcp` writes computed indicator series (`sma`/`rsi`/`pct_change`/…) into the `observations` table; daas/akshare/yfinance fetch and snapshot data into `data_snapshots` and `scraw_*` tables. `cron-mcp` can drive any MCP via a `--run-*` CLI branch. What's missing is the *reaction* layer: nothing evaluates "is this series now in a state I care about?" and nothing pushes that signal to a human. `alerts-mcp` is that layer — a small, cron-driven, stateful rule engine that reads the shared DB and dispatches to user-configured social/chat channels. It is deliberately *read-only* w.r.t. other MCPs' tables: it never writes to `observations`, only to its own `alert_rules` / `alert_events`.

**Stakeholders**: the project owner (runs alerts personally); reusable by any future consumer of the indicator pipeline.

**Constraints** (from `CLAUDE.md`): uv + Python 3.10+; one shared `mcp/daas.db`; shared `mcp/models/` schema package; per-MCP server loads dotenv from root first then own `.env` with `override=True`; no Alembic (tables via `Base.metadata.create_all`); cron CLI branches mirror `process-mcp --run-rule`; SQLite `PRAGMA foreign_keys=ON` per-connection where FKs exist.

## Goals / Non-Goals

**Goals:**
- Read indicator/observation (and `scraw_*`) series from `mcp/daas.db` and evaluate trigger rules on a cron schedule.
- A safe, dependency-free condition DSL (no `eval` of arbitrary code) covering thresholds, crossings, and pct-change.
- Pluggable notifier with 7 channels (Telegram, Discord, Slack, Twitter/X, DingTalk, Feishu, 企业微信), all credentials in root `.env`.
- Cooldown + state-change fire modes to prevent spam across cron ticks.
- Cron integration via `--run-rule` / `--run-all` CLI branches (process-mcp pattern); offline self-check.

**Non-Goals:**
- Not a general SQL browser (`dashboard-mcp.query_table` owns that). Inspection tools are alert-scoped.
- No LLM calls (no `LLM_*` keys); message bodies come from templates.
- No inbound/social scraping — outbound notifications only.
- No real-time push (no websockets/SSE); cron-tick granularity only.
- Does not modify other MCPs' tables; no schema migrations of existing tables.

## Decisions

### D1. Series source = unified `source_table` + validated `series_filter_json`
A rule points at `source_table` (default `observations`), a `series_filter_json` (key→value WHERE pairs, e.g. `{"source":"akshare","function_name":"stock_zh_a_hist","indicator":"close"}`), plus `date_column` and `value_column`. Identifiers (table + column names + filter keys) are validated against `^[A-Za-z_][A-Za-z0-9_]*$`; filter values are passed as bind params. This reuses the exact guard `process-mcp` applies to dynamic table/column SQL, so both `observations` mode and arbitrary `scraw_*` tables share one code path.
- **Alternative**: dedicated `observations_key` columns (`source`/`function_name`/`indicator`). Rejected — duplicates logic for `scraw_*` tables and forces schema changes when new series shapes appear.

### D2. Condition DSL = whitelisted `ast` walk, no `eval`
`expressions.evaluate(expr, ctx)` compiles with `ast.parse(expr, mode="eval")`, walks the tree, and allows only `BoolOp`/`UnaryOp`/`Compare`/`BinOp`/`Name`/`Constant`/`Call`. `Call` is restricted to a fixed function whitelist: `crosses_above(t)`, `crosses_below(t)`, `pct_change(n)`, `value(n)`, `avg(n)`, `min(n)`, `max(n)`. `Name` resolves to `latest` / `prev`. No `Attribute`, `Subscript`, comprehensions, or unknown names → cannot read secrets or call arbitrary code.
- **Alternatives**: `simpleeval` (new dep); raw `eval` (unacceptable — runs in the MCP server process with DB access); `ast.literal_eval` (no comparisons). The ast walk is dependency-free and auditable.

### D3. Fire model = `every_match` / `on_change` + `cooldown_seconds`, state on the rule row
`alert_rules.last_state` (nullable bool) and `last_fired_at` persist between cron ticks. `on_change` fires only on a false→true transition. `cooldown_seconds` gates `every_match` by comparing `now - last_fired_at`. One `alert_events` row per dispatch, with `channels_results_json` recording per-channel `{ok, error?}`. The cooldown check reads `last_fired_at` directly from the rule row (no join).
- **Alternative**: a separate dedup-window table. Rejected — `last_fired_at` on the rule is sufficient.

### D4. Notifier = ABC + registry; 7 adapters; env-driven `is_configured()`
`Notifier` ABC: `name`, `is_configured() -> bool`, `send(message: str, ctx: dict) -> dict`. `registry.send(channel, message, ctx)` looks up the adapter; missing/unconfigured channels return `{ok: False, error: "not configured"}` and are recorded in `channels_results_json` (so the user sees their Slack webhook is missing). `list_channels` returns `{channel, configured, missing_keys}` with secret values redacted. New channel = one file + one registry line.
- Channel specifics:
  - **Telegram**: `ALERTS_TELEGRAM_BOT_TOKEN` + `ALERTS_TELEGRAM_CHAT_ID` (default chat; per-rule override in `channels_json`). POST `/sendMessage`.
  - **Discord**: `ALERTS_DISCORD_WEBHOOK_URL`. One POST.
  - **Slack**: `ALERTS_SLACK_WEBHOOK_URL`. One POST.
  - **DingTalk**: `ALERTS_DINGTALK_WEBHOOK_URL` + optional `ALERTS_DINGTALK_SECRET` (HMAC-SHA256 sign, `&timestamp=`).
  - **Feishu**: `ALERTS_FEISHU_WEBHOOK_URL` + optional `ALERTS_FEISHU_SECRET` (HMAC-SHA256 in `X-Lark-Signature`).
  - **企业微信 (WeCom)**: `ALERTS_WECOM_WEBHOOK_URL` + optional `ALERTS_WECOM_SECRET`.
  - **Twitter/X**: OAuth 1.0a user context — `ALERTS_TWITTER_CONSUMER_KEY`/`_SECRET` + `ALERTS_TWITTER_ACCESS_TOKEN`/`_SECRET`. (See D5.)

### D5. Twitter/X via OAuth 1.0a hand-rolled over httpx (no new dep)
OAuth 1.0a HMAC-SHA1 request signing is a ~40-line stdlib helper (`hmac`/`hashlib`/`urllib.parse`). Avoids pulling `requests-oauthlib` + `requests`. The self-check stubs the network so no real tweet fires. If signing proves fragile, swap in `requests-oauthlib` behind the same `Notifier` interface (one-file change).
- **Alternatives**: OAuth 2.0 PKCE (token refresh + persistence — heavier); `requests-oauthlib` (new dep). Deferred.

### D6. Message rendering = `string.Template` (safer than `.format`)
`string.Template(message_template).safe_substitute(latest=…, prev=…, date=…, rule_name=…, source=…, indicator=…, value=…, pct_change=…). `safe_substitute` leaves unknown placeholders rather than raising; `string.Template` cannot access object attributes (unlike `str.format`), so a template cannot exfiltrate. Documented variable list.

### D7. Schema = 2 tables, `Base.metadata.create_all`, no Alembic
`AlertRule` and `AlertEvent` added to `mcp/models/`. `alert_events.rule_id` is a real FK `ON DELETE CASCADE` (deleting a rule drops its history). `PRAGMA foreign_keys=ON` per-connection (same as daas-mcp). Matches every sibling MCP's no-Alembic convention.

### D8. Cron CLI branches mirror process-mcp exactly
`python server.py --run-rule <name>` (one rule) and `--run-all` (every enabled rule, single tick). Each prints a JSON summary and exits, so `cron-mcp` runs it as a shell task. The cron task command: `uv run --directory /Users/chengsishi/code/cli-anything/mcp/alerts-mcp python server.py --run-rule <name>`. `--run-all` is sequential with per-rule try/except (one failure does not stop the rest).

## Risks / Trade-offs

- **Twitter OAuth 1.0a signing fragility** → hand-rolled HMAC-SHA1 is well-trodden but error-prone (parameter encoding, base string). Mitigation: a dedicated unit test against a known RFC 5849 vector; adapter isolated so `requests-oauthlib` can replace it one-file if it breaks.
- **Webhook rate limits / bans (DingTalk ~20/min, etc.))** → cooldown + `on_change` default keep volume low; per-channel failures recorded in `channels_results_json` and surfaced by `list_channels` health. Mitigation: document limits in adapter docstrings.
- **Secret leakage through `list_channels`** → adapter `is_configured()` returns booleans only; `list_channels` never returns env values, only `missing_keys` *names*. Mitigation: self-check asserts no secret string appears in `list_channels` output.
- **Condition DSL escape** → ast whitelist disallows `Attribute`, `Call` (except whitelist), `Subscript`, comprehensions. Mitigation: self-check fuzzes the evaluator with a battery of malicious expressions (`__import__`, `os.system`, attribute access) — all must raise `ExpressionError`.
- **Reading stale `observations`** → no schema change to `observations`; rules read whatever `process-mcp` last wrote. Mitigation: rules carry their own `date_column`; `get_series_latest` orders by it. Alert freshness is bounded by the indicator cron cadence (documented).
- **`on_change` across restarts** → `last_state` persisted on the rule row; a cron-mcp restart resumes correctly. Mitigation: self-check covers the false→true→false→true cycle.

## Migration Plan

1. Add `AlertRule`/`AlertEvent` to `mcp/models/`; `Base.metadata.create_all` creates the 2 tables on first start (idempotent — existing `daas.db` gains only the new tables).
2. Implement `mcp/alerts-mcp/` + register in `.mcp.json`.
3. Run `selfcheck.py` (temp DB, stubbed notifiers — no network, no real posts).
4. Seed a sample rule via `create_alert_rule` + a `cron-mcp` schedule (manual, user-driven). No automatic rules shipped.
5. **Rollback**: remove the `.mcp.json` entry + `DROP TABLE alert_events; DROP TABLE alert_rules;` — no other MCP references them.

## Open Questions

- Per-rule `chat_id`/webhook override vs. one global env default. **Decision**: support both — per-rule override lives in `channels_json` (e.g. `{"telegram": {"chat_id": "…"}}`), falling back to the env default. The same mechanism can carry Slack/Discord alt webhooks per rule later.
- `--run-all` parallel vs sequential. **Decision**: sequential (cron ticks are infrequent; parallel adds concurrency complexity and risk of webhook rate-limit storms). One rule failure does not stop the rest.
