# Implementation Plan: DAAS Provider

## Technical Context

- **Language/Version**: Python >=3.10
- **Primary Dependencies**: click, pandas, akshare (existing), world-bank-data (or similar), ckanapi, requests, sqlalchemy, fastmcp
- **Storage**: SQLite (follows existing pattern at `mcp/daas_registry.db`), plus a registry JSON
- **Testing**: pytest (match existing harness pattern — `@pytest.mark.skipif` for optional deps)
- **Target Platform**: macOS/Linux CLI, MCP stdio transport
- **Project Type**: multi-package monorepo (daas-agent-harness + daas-mcp + leader-mcp extension)
- **Performance Goals**: function discovery <100ms, data fetch varies by source (5-30s typical)
- **Constraints**: must follow existing harness pattern (PEP 420 namespace `cli_anything/daas/`), must integrate with leader-mcp unified registry
- **Scale/Scope**: 4+ data sources initially (akshare, world bank, ckan, chinese statistics), extensible for more

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate | Status | Notes |
|------|--------|-------|
| Follows existing harness pattern | ✅ PASS | Mirrors `akshare-agent-harness/` structure |
| PEP 420 namespace package | ✅ PASS | `cli_anything/daas/` (no `__init__.py`) |
| uv for dependency management | ✅ PASS | `uv sync`, `uv run` |
| MCP stdio transport | ✅ PASS | FastMCP server in `mcp/daas-mcp/` |
| SQLite for persistence | ✅ PASS | `mcp/daas_registry.db` + leader_mcp.db extension |
| Tests with pytest | ✅ PASS | Unit + E2E CLI tests |
| No modifications to CLI-Anything/ | ✅ PASS | Custom work in `daas-agent-harness/` |

## Project Structure

### Source Code

```
daas-agent-harness/                  # CLI wrapper (mirrors akshare-agent-harness)
├── pyproject.toml
├── setup.py
├── cli_anything/
│   └── daas/                        # PEP 420 namespace (no __init__.py)
│       ├── __init__.py              # (empty, namespace package)
│       ├── cli.py                   # Click CLI: search, call, list-sources
│       ├── registry.py              # Registry loader (JSON + DB fallback)
│       ├── sources/                 # Data source adapters
│       │   ├── __init__.py
│       │   ├── base.py              # Abstract SourceAdapter
│       │   ├── akshare_source.py    # Wraps akshare (existing)
│       │   ├── worldbank_source.py  # World Bank API
│       │   ├── ckan_source.py       # CKAN portal adapter
│       │   └── cnstats_source.py    # Chinese National Statistics
│       ├── metadata/
│       │   └── registry.json        # Discovered functions + columns
│       └── scripts/
│           └── store_registry.py    # Script to scrape/store registry data
├── skills/
│   └── cli-anything-daas/
│       └── SKILL.md                 # Skill definition for Claude
└── tests/
    ├── test_cli.py
    ├── test_registry.py
    └── test_sources.py

mcp/daas-mcp/                        # Unified multi-source MCP server
├── server.py                        # FastMCP entry point
├── daas_tools.py                    # MCP tools: search, fetch, list_sources
├── daas_database.py                 # SQLAlchemy models + session
├── models.py                        # ORM models (function, column, source)
├── registry_service.py              # Registry CRUD operations
├── sources/
│   └── __init__.py
└── pyproject.toml

mcp/ckan-mcp/                        # Standalone CKAN MCP server
├── server.py                        # FastMCP entry point (5 tools)
├── pyproject.toml
├── .env                             # CKAN_DATABASE_URL, CKAN_PORTAL_URL, proxy
└── .env.example

mcp/cnstats-mcp/                     # Standalone Chinese Statistics MCP server
├── server.py                        # FastMCP entry point (5 tools)
├── pyproject.toml
├── .env                             # CNSTATS_DATABASE_URL, proxy
└── .env.example

mcp/worldbank-mcp/                   # Standalone World Bank MCP server
├── server.py                        # FastMCP entry point (5 tools)
├── pyproject.toml
├── .env                             # WORLDBANK_DATABASE_URL, proxy
└── .env.example

mcp/populate_daas.py                 # Script: populate daas.db from source adapters
mcp/daas.db                          # SQLite: sources, functions, function_columns tables
```

## Phase 0: Research

### Research Tasks

1. **World Bank API**: What's the best Python approach — `wbgapi` package vs raw `requests` to `api.worldbank.org/v2/`?
2. **CKAN API**: Standard `ckanapi` package vs raw requests. Which CKAN portals are useful (data.gov, etc.)?
3. **Chinese National Statistics**: What's the accessible data source? `akshare` already covers some — what's additive?
4. **Registry DB Schema**: How to extend `leader_mcp.db` unified schema vs separate DB?
5. **Source Adapter Pattern**: Abstract base class design for pluggable data sources.

### Research Findings

See `research.md` for detailed findings.

## Phase 1: Design

### Data Model

See `data-model.md` for entity definitions, relationships, and validation rules.

### Contracts

See `contracts/` directory for:
- `cli-contract.md` — CLI command interface
- `mcp-tools.md` — MCP tool definitions

### Quickstart

See `quickstart.md` for end-to-end validation scenarios.

## Constitution Re-Check (Post-Design)

| Gate | Status | Notes |
|------|--------|-------|
| No unnecessary abstraction | ✅ PASS | Single SourceAdapter base class, not per-source factory |
| Stdlib where possible | ✅ PASS | `sqlite3` for simple cases, SQLAlchemy for MCP server |
| Follows existing patterns | ✅ PASS | Mirrors akshare harness + leader-mcp structure |
| Tests cover core paths | ✅ PASS | CLI E2E + registry + one source adapter |

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that need justification.

None.
