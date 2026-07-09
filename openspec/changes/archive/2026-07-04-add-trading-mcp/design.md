## Context

The project already has `leader-mcp` (unified registry), `akshare-mcp` (live financial data), and `cron-mcp` (scheduling). Adding a trading analysis MCP server fills the gap between raw data and actionable insights.

Current state:
- `mcp/leader-mcp/` — FastMCP server, CrewAI optional, queries `daas.db`
- `mcp/akshare-mcp/` — FastMCP server, wraps AKShare for live data
- `mcp/daas.db` — SQLite with `functions`, `function_columns`, `data_snapshots` tables
- No agent that reasons about stocks with structured multi-perspective analysis

Constraints:
- Must follow existing MCP server patterns (FastMCP entry, `pyproject.toml`, `uv` for deps)
- Must register tools in `daas.db` so `leader-mcp` can discover them
- CrewAI is already an optional dependency of `leader-mcp` — reuse, don't duplicate

## Goals / Non-Goals

**Goals:**
- Provide 5 MCP tools for Claude Code: `analyze_ticker`, `bull_bear_debate`, `risk_debate`, `full_pipeline`, `list_personas`
- Five famous investor personas with distinct system prompts producing independent analyses
- TradingAgents-style pipeline: analysts → debate → trader → risk → portfolio decision
- Structured outputs (Pydantic) so results are machine-readable
- Self-registration in `daas.db` on startup (harness="trading")

**Non-Goals:**
- LangGraph orchestration (v1 uses CrewAI, graph adds complexity without new capability)
- Real-time streaming of agent debate (tools return final structured reports)
- New database tables (personas live in code, tools in existing `functions` table)
- Backtesting or portfolio tracking (future work)
- LLM provider abstraction — default to whatever the user has configured; agent prompts are provider-agnostic

## Decisions

### Decision 1: CrewAI over raw LLM calls

**Chosen:** CrewAI for agent orchestration.
**Alternatives:** Raw litellm calls, LangGraph.

CrewAI is already used by `leader-mcp/leader_crew.py`. It provides agent role/goal/backstory DSL that maps directly to investor personas. LangGraph adds graph compilation overhead; raw calls require building orchestration from scratch. CrewAI's hierarchical process fits the pipeline pattern (manager delegates to specialists).

### Decision 2: Personas as system prompts, not fine-tuned models

**Chosen:** Each investor persona is a CrewAI Agent with a detailed system prompt encoding their philosophy.
**Alternatives:** Fine-tuned models, RAG over investor writings.

Fine-tuning requires training data and model hosting. RAG over Buffett letters is over-engineered for v1. System prompts are zero-cost, trivially editable, and surprisingly effective at role-playing investing styles.

### Decision 3: One MCP server, not split

**Chosen:** Single `trading-mcp` server with all tools.
**Alternatives:** Separate servers for personas vs pipeline.

All tools share the same agent definitions and schemas. Splitting would mean two servers importing from a shared lib — more config surface for zero benefit.

### Decision 4: Tools call akshare-mcp via Python import, not MCP

**Chosen:** Agents import `akshare` directly for data, same pattern as `leader_tools.save_snapshot`.
**Alternatives:** Call akshare-mcp via MCP protocol.

MCP-to-MCP calls add serialization overhead and error surface. Agents need raw dataframes/pandas objects for analysis, not JSON strings. Direct import is simpler and already proven in the codebase.

### Decision 5: Register tools in existing `functions` table

**Chosen:** On startup, `trading-mcp` upserts rows in `daas.db` with `harness="trading"`.
**Alternatives:** Separate `agents` table, no registration.

A separate table adds schema migration burden. No registration means leader-mcp can't discover trading tools. Upserting into `functions` is idempotent and follows the existing `import_harness_registry` pattern.

## Architecture

```
mcp/trading-mcp/
├── pyproject.toml          # deps: fastmcp, crewai, pydantic, akshare
├── server.py               # FastMCP entry, registers 5 tools
├── schemas.py              # Pydantic models for structured outputs
└── agents/
    ├── __init__.py
    ├── personas.py          # 5 investor persona agent factories
    ├── analysts.py          # fundamentals/sentiment/news/market analyst factories
    ├── debators.py          # bull/bear researcher factories
    ├── trader.py            # trader agent factory
    └── risk_manager.py      # aggressive/conservative/neutral + PM factories
```

### Tool → Agent mapping

```
analyze_ticker(ticker)     → 5 persona agents in parallel → merged report
bull_bear_debate(ticker)   → bull + bear researchers → debate verdict
risk_debate(ticker, prop)  → aggressive + conservative + neutral → PM decision
full_pipeline(ticker)      → analysts → debate → trader → risk → PM decision
list_personas()            → static list of 5 personas + philosophies
```

### Persona prompt structure

Each persona agent gets:
1. **Role**: "{Investor Name} — {Style}"
2. **Goal**: Specific analysis objective phrased in their voice
3. **Backstory**: 3-5 sentences capturing their philosophy, key concepts, and decision framework
4. **Tools**: Access to akshare data functions (stock history, financials, etc.)
5. **Expected output**: Structured `PersonaAnalysis` (ticker, action, conviction 1-10, thesis, key metrics, risks)

## Risks / Trade-offs

- [Risk] LLM quality varies by provider → Mitigation: prompts are provider-agnostic, no provider-specific reasoning params in v1
- [Risk] CrewAI import fails on Python 3.14 (known chromadb incompatibility) → Mitigation: document the constraint, same as leader-mcp
- [Risk] AKShare API rate limits when 5 personas query simultaneously → Mitigation: sequential queries with small delays; v1 doesn't need parallel
- [Risk] Persona analyses may hallucinate data if akshare returns empty → Mitigation: agents are instructed to state "insufficient data" rather than fabricate

## Open Questions

- Should `full_pipeline` run synchronously or return a task ID for async? (v1: synchronous, simple)
- Should persona analyses include Chinese translations? (v1: English-only, add later if needed)
