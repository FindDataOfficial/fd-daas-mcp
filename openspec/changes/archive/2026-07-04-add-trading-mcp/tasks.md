## 1. Scaffold

- [x] 1.1 Create `mcp/trading-mcp/` directory structure with `pyproject.toml`, `server.py`, `schemas.py`, and `agents/` package
- [x] 1.2 Configure `pyproject.toml` with dependencies: `fastmcp>=2.0`, `crewai`, `pydantic`, `akshare`
- [x] 1.3 Create `agents/__init__.py` with re-exports

## 2. Schemas

- [x] 2.1 Define `PersonaAnalysis` Pydantic model (ticker, investor_name, action, conviction, thesis, key_metrics, risks)
- [x] 2.2 Define `PortfolioDecision` Pydantic model (ticker, rating, executive_summary, investment_thesis, risk_assessment)
- [x] 2.3 Define `TraderProposal` Pydantic model (action, reasoning, entry_price, stop_loss, position_sizing)
- [x] 2.4 Define shared enums: `PortfolioRating` (Buy/Overweight/Hold/Underweight/Sell), `TraderAction` (Buy/Hold/Sell)

## 3. Agent factories

- [x] 3.1 Implement `agents/personas.py` — five `create_*_persona()` factory functions, each returning a CrewAI Agent with role/goal/backstory
- [x] 3.2 Implement `agents/analysts.py` — four analyst factories (fundamentals, sentiment, news, market/technical)
- [x] 3.3 Implement `agents/debators.py` — bull researcher, bear researcher, research manager factories
- [x] 3.4 Implement `agents/trader.py` — trader agent factory
- [x] 3.5 Implement `agents/risk_manager.py` — aggressive/conservative/neutral risk analyst + portfolio manager factories

## 4. MCP tools

- [x] 4.1 Implement `list_personas()` tool — returns static list of 5 personas with philosophies
- [x] 4.2 Implement `analyze_ticker(ticker)` tool — runs 5 personas in parallel, merges results
- [x] 4.3 Implement `bull_bear_debate(ticker, thesis)` tool — bull vs bear debate with research manager verdict
- [x] 4.4 Implement `risk_debate(ticker, proposal_json)` tool — three-way risk debate with PM decision
- [x] 4.5 Implement `full_pipeline(ticker)` tool — end-to-end pipeline (analysts → debate → trader → risk → decision)

## 5. Server entry point

- [x] 5.1 Implement `server.py` — FastMCP app, register all 5 tools, auto-register in daas.db on startup
- [x] 5.2 Implement `_register_in_registry()` — upsert tool entries into `functions` table with `harness="trading"`

## 6. Testing

- [x] 6.1 Write `test_personas.py` — verify all 5 persona agents are creatable and produce valid outputs
- [x] 6.2 Write `test_pipeline.py` — verify full pipeline runs end-to-end for a known ticker
- [x] 6.3 Write `test_server.py` — verify all tools are registered and callable
