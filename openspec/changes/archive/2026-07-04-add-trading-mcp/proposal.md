## Why

The project has a rich financial data layer (AKShare via `akshare-mcp`, unified registry via `leader-mcp`) but no intelligent agents that can analyze stocks with distinct investing philosophies. Borrowing TradingAgents' proven multi-agent pipeline (analysts → debate → trader → risk → decision) and adding famous investor personas gives users structured, multi-perspective investment analysis directly from Claude Code.

## What Changes

- New `mcp/trading-mcp/` MCP server (FastMCP) with 5 MCP tools
- Five famous investor personas: Buffett (value), Soros (macro), Lynch (GARP), Dalio (all-weather), Simons (quant)
- TradingAgents-style role pipeline: fundamentals/sentiment/news/market analysts, bull-bear debate, trader, aggressive/conservative/neutral risk debate, portfolio manager
- Structured output schemas (Pydantic) for trade proposals and decisions
- Registration in `daas.db` as `harness="trading"` so leader-mcp can discover the agent tools
- No new database tables — agent personas live in code, tools are registered via existing `functions` table

## Capabilities

### New Capabilities

- `trading-mcp-server`: FastMCP server exposing trading analysis tools to Claude Code
- `investor-personas`: Five famous investor agents with distinct philosophies, each producing independent BUY/HOLD/SELL analyses
- `trading-pipeline`: TradingAgents-style multi-agent pipeline (analysts → debate → trader → risk → decision)

### Modified Capabilities

None — this is entirely new.

## Impact

- New directory: `mcp/trading-mcp/` (~8 files)
- New Python dependencies: `crewai` (already used by leader-mcp), `pydantic`
- Existing files touched: `mcp/leader-mcp/unified_models.py` (register trading tools in functions table on startup)
- `mcp/daas.db` gets new rows under `harness="trading"` (auto-registered, idempotent)
