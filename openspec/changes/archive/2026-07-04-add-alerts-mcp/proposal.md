## Why

The project can compute indicator series (`sma`, `rsi`, `pct_change`, …) into the shared `observations` table via `process-mcp`, and fetch/store market data via the daas/akshare/yfinance MCPs. But nothing *watches* those series. Today a user has to poll tables by hand to notice that an RSI crossed 70, a price moved ≥5%, or a computed signal flipped — so the data pipeline ends silently. `alerts-mcp` closes the loop: it inspects data in the shared `mcp/daas.db`, evaluates user-defined trigger rules on a schedule, and pushes notifications to the social/chat channels the user already uses, with all channel credentials managed in `.env`.

## What Changes

- **New MCP `alerts-mcp`** (FastMCP, stdio) under `mcp/alerts-mcp/`, registered in `.mcp.json`. Same layout conventions as `process-mcp` / `edgartools-mcp`.
- **Data inspection tools** (alert-focused, not a general SQL browser — `dashboard-mcp` already owns that): `list_series` (distinct `source`/`function_name`/`indicator` triples in `observations` + any `scraw_*` table) and `get_series_latest` (latest N values for a series) so users can explore exactly what to alert on.
- **Trigger rules**: a persisted rule binding `(datasource, function_name, indicator, condition, channels[], message_template, cooldown, fire_mode, enabled)`. CRUD tools: `create_alert_rule`, `list_alert_rules`, `get_alert_rule`, `update_alert_rule`, `delete_alert_rule`.
- **Safe condition evaluator**: a small expression engine over a series' latest/last-N values — comparisons (`>`, `<`, `>=`, `<=`, `==`, `!=`, `crosses_above`, `crosses_below`), `and`/`or`, thresholds, and `pct_change` over a window. No `eval()` of arbitrary code; identifiers validated against `^[A-Za-z_][A-Za-z0-9_]*$` (same guard pattern as `process-mcp` dynamic SQL).
- **Pluggable notifier + 7 channel adapters**: Telegram (Bot API), Discord webhook, Slack webhook, Twitter/X (OAuth2), DingTalk (钉钉) webhook, Feishu (飞书) webhook, 企业微信 (WeCom) webhook. Each adapter implements one `Notifier` interface (`send(message) -> result`); new channels are one file.
- **`.env` key management**: all channel credentials read from root `.env` under per-channel prefixes (`ALERTS_TELEGRAM_BOT_TOKEN`, `ALERTS_DISCORD_WEBHOOK_URL`, `ALERTS_DINGTALK_WEBHOOK_URL`, `ALERTS_FEISHU_WEBHOOK_URL`, `ALERTS_WECOM_WEBHOOK_URL`, `ALERTS_SLACK_WEBHOOK_URL`, `ALERTS_TWITTER_*`). A `list_channels` tool reports which channels are configured vs. missing keys **without leaking secrets**.
- **Cron integration**: `python server.py --run-rule <name>` CLI branch evaluates one rule in-process and dispatches notifications; wire via `cron-mcp` `create_task` + `create_schedule` (same pattern as `process-mcp --run-rule`). A `--run-all` branch evaluates every enabled rule (for a single cron tick).
- **Dedup / cooldown / fire modes**: an `alert_events` table records every dispatch; rules respect a `cooldown_seconds` window and a `fire_mode` of `every_match` or `on_change` (fire once per crossing) to avoid spam across cron ticks.
- **Schema**: 2 new tables (`alert_rules`, `alert_events`) in `mcp/daas.db` via `DAAS_DATABASE_URL`, created via `Base.metadata.create_all` (no Alembic). New models added to `mcp/models/`.
- **Self-check**: `selfcheck.py` with a temp DB + a stub notifier (no network, no real social posts) exercising rule CRUD → condition eval → dispatch → cooldown.

## Capabilities

### New Capabilities
- `alerts-mcp-server`: MCP that inspects `mcp/daas.db` series, evaluates persisted trigger rules over `observations`/`scraw_*` data on a cron schedule, and dispatches notifications to configurable social/chat channels (Telegram, Discord, Slack, Twitter/X, DingTalk, Feishu, 企业微信) with credentials managed in root `.env`.

### Modified Capabilities
<!-- None. alerts-mcp reads `observations` produced by `process-mcp-indicators` and tables produced by daas/pipeline MCPs, but does not change their requirements. -->

## Impact

- **New code**: `mcp/alerts-mcp/` — `server.py`, `alert_tools.py`, `alert_database.py`, `expressions.py`, `notifiers/` (`base.py` + 7 adapters + `registry.py`), `selfcheck.py`; model additions in `mcp/models/`.
- **`.mcp.json`**: register `alerts-mcp` (`uv run --directory mcp/alerts-mcp python server.py`).
- **Root `.env`**: new `ALERTS_*` env vars for 7 channels; no LLM keys required (no LLM call).
- **`mcp/daas.db`**: 2 new tables (`alert_rules`, `alert_events`) via `Base.metadata.create_all`.
- **Dependencies**: `fastmcp`, `httpx`, `python-dotenv`, `sqlalchemy`, `mcp-models` (all already in use by sibling MCPs); Twitter/X OAuth2 hand-rolled over `httpx` (no new heavy dep — `requests-oauthlib` optional).
- **No breaking changes.** Reads existing `observations` / `scraw_*` tables; does not modify any other MCP.
