# Tasks: DAAS Provider

**Input**: Design documents from `/specs/001-daas-provider/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in spec. Minimal smoke tests included (matching existing akshare harness pattern).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding — directory structure, package config, dependencies

- [ ] T001 Create `daas-agent-harness/` directory structure per plan.md (cli_anything/daas/, sources/, metadata/, scripts/, skills/, tests/)
- [ ] T002 [P] Create `daas-agent-harness/pyproject.toml` with dependencies: click>=8.0, pandas>=1.0, sqlalchemy>=1.4, plus optional: akshare, wbgapi, ckanapi, requests
- [ ] T003 [P] Create `daas-agent-harness/setup.py` with entry_points console_script `cli-anything-daas=cli_anything.daas.cli:cli`, namespace packages, and extras_require (dev, repl)
- [ ] T004 [P] Create `mcp/daas-mcp/` directory structure per plan.md (server.py, daas_tools.py, daas_database.py, models.py, registry_service.py, sources/, pyproject.toml)
- [ ] T005 [P] Create `mcp/daas-mcp/pyproject.toml` with dependencies: fastmcp, sqlalchemy>=2.0, pandas

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on — DB models, database singleton, source base class, registry service

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create SQLAlchemy models (Source, Function, FunctionColumn) in `daas-agent-harness/cli_anything/daas/core/models.py` per data-model.md — include toDict(), relationships, unique constraints
- [ ] T007 [P] Create database singleton (SQLAlchemy engine + session factory) in `daas-agent-harness/cli_anything/daas/core/database.py` — default to `mcp/daas_registry.db`, support DATABASE_URL env override
- [ ] T008 [P] Create `SourceAdapter` abstract base class in `daas-agent-harness/cli_anything/daas/sources/base.py` with three abstract methods: `discover()`, `fetch(function_name, **params)`, `columns(function_name)`
- [ ] T009 [P] Create DAAS exception classes in `daas-agent-harness/cli_anything/daas/core/exceptions.py` — `SourceUnavailableError`, `FunctionNotFoundError`, `ParameterError`
- [ ] T010 Create RegistryService class in `daas-agent-harness/cli_anything/daas/core/registry.py` — mirrors akshare pattern: `list_functions()`, `search_functions(query)`, `get_function_info(name)`, `get_categories()`, `get_category_functions(cat)`, backed by SQLAlchemy session
- [ ] T011 Create output formatting utility in `daas-agent-harness/cli_anything/daas/utils/output.py` — `format_output(result, json_mode)` that handles DataFrame → table or JSON
- [ ] T012 [P] Create initial `daas-agent-harness/cli_anything/daas/__init__.py` (empty namespace package, PEP 420)

**Checkpoint**: Foundation ready — models, DB, source adapter ABC, registry service, output utils all in place

---

## Phase 3: User Story 1 - Discover and search data functions across all sources (Priority: P1) 🎯 MVP

**Goal**: CLI can list sources, search functions, show categories — even before any data fetching works

**Independent Test**: `cli-anything-daas search GDP` returns matching functions from all sources

### Implementation for User Story 1

- [ ] T013 [US1] Create `SourceConfig` dataclass and source loader in `daas-agent-harness/cli_anything/daas/sources/config.py` — loads source definitions (name, label, description, URL, enabled, config) from a YAML/JSON config, checks if optional deps are installed
- [ ] T014 [P] [US1] Create AKShare source adapter in `daas-agent-harness/cli_anything/daas/sources/akshare_source.py` — wraps akshare registry for `discover()` and `columns()`, defers `fetch()` to Phase 4 (US2)
- [ ] T015 [P] [US1] Create World Bank source adapter stub in `daas-agent-harness/cli_anything/daas/sources/worldbank_source.py` — `discover()` returns curated list of ~20 key indicators (GDP, population, trade, etc.) even without wbgapi installed
- [ ] T016 [P] [US1] Create CKAN source adapter stub in `daas-agent-harness/cli_anything/daas/sources/ckan_source.py` — `discover()` returns curated list of CKAN functions, configurable portal URL
- [ ] T017 [P] [US1] Create Chinese Statistics source adapter stub in `daas-agent-harness/cli_anything/daas/sources/cnstats_source.py` — `discover()` returns curated list of NBS macro indicators
- [ ] T018 [US1] Create CLI entry point in `daas-agent-harness/cli_anything/daas/cli.py` — Click group with `--json` flag, `list-sources`, `search`, `categories`, `describe` commands, plus REPL mode (depends on T010, T013)
- [ ] T019 [US1] Implement `list-sources` command — query source config, show table with name, label, function count, enabled/installed status
- [ ] T020 [US1] Implement `search` command — delegate to RegistryService.search_functions(), format results as table or JSON
- [ ] T021 [US1] Implement `categories` command — delegate to RegistryService.get_categories(), show counts per source
- [ ] T022 [US1] Implement `describe` command — delegate to RegistryService.get_function_info(), show parameters and columns
- [ ] T023 [US1] Implement REPL mode — mirrors akshare pattern: prompt_toolkit session with history, commands: search, list-sources, categories, describe, help, exit

**Checkpoint**: User Story 1 fully functional — `cli-anything-daas search GDP` works, all discovery commands operational

---

## Phase 4: User Story 2 - Fetch data from any source (Priority: P1) 🎯 MVP

**Goal**: CLI `call` command routes to correct source adapter and returns pandas DataFrame

**Independent Test**: `cli-anything-daas call worldbank_gdp country=CN date=2020:2023` returns a DataFrame

### Implementation for User Story 2

- [ ] T024 [US2] Implement `fetch()` in AKShare source adapter in `daas-agent-harness/cli_anything/daas/sources/akshare_source.py` — import akshare, call function by name with params, return DataFrame
- [ ] T025 [P] [US2] Implement `fetch()` in World Bank source adapter in `daas-agent-harness/cli_anything/daas/sources/worldbank_source.py` — use wbgapi, map function names to indicator codes, return DataFrame
- [ ] T026 [P] [US2] Implement `fetch()` in CKAN source adapter in `daas-agent-harness/cli_anything/daas/sources/ckan_source.py` — use ckanapi, search datasets, return DataFrame
- [ ] T027 [P] [US2] Implement `fetch()` in Chinese Statistics source adapter in `daas-agent-harness/cli_anything/daas/sources/cnstats_source.py` — use akshare macro functions, return DataFrame
- [ ] T028 [US2] Create `SourceRouter` in `daas-agent-harness/cli_anything/daas/sources/router.py` — resolves `source_functionname` → adapter + function, handles namespace parsing, delegates to adapter.fetch()
- [ ] T029 [US2] Implement `call` command in `daas-agent-harness/cli_anything/daas/cli.py` — parse `key=value` args, route via SourceRouter, format output via output.py, handle errors (depends on T028)
- [ ] T030 [US2] Add graceful degradation — when optional dep is missing, `call` shows install hint instead of ImportError; when source is down, show SourceUnavailableError with clear message
- [ ] T031 [US2] Add parameter validation before calling source — check required params are present, warn on unknown params, show expected params on mismatch

**Checkpoint**: User Stories 1 AND 2 both work — full CLI with search + call + REPL

---

## Phase 5: User Story 3 - Store and persist function metadata (Priority: P2)

**Goal**: `store_registry.py` discovers all functions, persists to JSON + SQLite, integrates with leader-mcp

**Independent Test**: Run `store_registry.py`, verify `registry.json` and `daas_registry.db` are populated, leader-mcp can query DAAS functions

### Implementation for User Story 3

- [ ] T032 [US3] Create `store_registry.py` in `daas-agent-harness/cli_anything/daas/scripts/store_registry.py` — iterates all enabled sources, calls `discover()`, upserts functions + columns into DB, also writes `registry.json`
- [ ] T033 [US3] Implement `registry.json` export — standard format matching akshare pattern: `{function_name: {category, description, parameters, columns, source}}`
- [ ] T034 [US3] Implement DB upsert logic — idempotent: existing (source, function) pairs update, new ones insert, removed functions optionally soft-delete
- [ ] T035 [US3] Add `--source` and `--dry-run` flags to `store_registry.py` — filter by source, preview without writing
- [ ] T036 [US3] Verify leader-mcp integration — run `import_harness_registry("daas", "registry.json")` against leader_mcp.db, confirm `search_functions` returns DAAS results alongside akshare

**Checkpoint**: Registry persistence works — data discoverable via leader-mcp unified search

---

## Phase 6: User Story 4 - Claude Code skill and MCP server (Priority: P2)

**Goal**: `/cli-anything-daas` skill works in Claude Code, daas-mcp server responds to tool calls

**Independent Test**: In Claude Code, `/cli-anything-daas search GDP` returns results

### Implementation for User Story 4

- [ ] T037 [US4] Create `skills/cli-anything-daas/SKILL.md` in `daas-agent-harness/skills/cli-anything-daas/SKILL.md` — following akshare skill pattern: prerequisites, installation, quick start, command groups, agent guidance
- [ ] T038 [P] [US4] Create SQLAlchemy models for daas-mcp in `mcp/daas-mcp/models.py` — Source, Function, FunctionColumn (same schema as harness, separate DB for MCP independence)
- [ ] T039 [P] [US4] Create database singleton for daas-mcp in `mcp/daas-mcp/daas_database.py` — default to `mcp/daas_registry.db`, support DATABASE_URL override
- [ ] T040 [P] [US4] Create registry_service for daas-mcp in `mcp/daas-mcp/registry_service.py` — query layer over models, same API surface as harness registry
- [ ] T041 [US4] Create `list_sources` MCP tool in `mcp/daas-mcp/daas_tools.py` — returns all sources with function counts
- [ ] T042 [US4] Create `search_functions` MCP tool in `mcp/daas-mcp/daas_tools.py` — search by query, optional source filter, returns function summaries
- [ ] T043 [US4] Create `get_function_detail` MCP tool in `mcp/daas-mcp/daas_tools.py` — returns full function detail with params and columns
- [ ] T044 [US4] Create `fetch_data` MCP tool in `mcp/daas-mcp/daas_tools.py` — routes to source adapter, executes fetch, returns JSON-serialized DataFrame
- [ ] T045 [US4] Create `list_categories` MCP tool in `mcp/daas-mcp/daas_tools.py` — returns categories across all sources
- [ ] T046 [US4] Create daas-mcp server entry point in `mcp/daas-mcp/server.py` — FastMCP app, register all tools from daas_tools.py, stdio transport, resolve harness path for imports
- [ ] T047 [US4] Create source fetchers in `mcp/daas-mcp/sources/` — akshare_fetcher.py, worldbank_fetcher.py, ckan_fetcher.py, cnstats_fetcher.py (thin wrappers that import from harness sources/)

**Checkpoint**: Skill + MCP server fully operational — Claude Code can discover and fetch DAAS data

---

## Phase 7: User Story 5 - Extensible source adapter (Priority: P3)

**Goal**: Prove the adapter pattern works end-to-end; ensure all 4 sources implement the full interface

**Independent Test**: Create a test adapter, register it, verify `list-sources` shows it and `call` works

### Implementation for User Story 5

- [ ] T048 [P] [US5] Finalize AKShare adapter — ensure `discover()`, `fetch()`, `columns()` all work; add graceful handling when akshare not installed
- [ ] T049 [P] [US5] Finalize World Bank adapter — full `discover()` with wbgapi indicator enumeration, `fetch()` with country/date params, `columns()` from fetched DataFrame
- [ ] T050 [P] [US5] Finalize CKAN adapter — full `discover()` from configured portal, `fetch()` with dataset search/retrieval, `columns()` from result schema
- [ ] T051 [P] [US5] Finalize CNStats adapter — full `discover()` with curated NBS indicators, `fetch()` via akshare macro functions, `columns()` from result
- [ ] T052 [US5] Add `sources/__init__.py` with `get_adapter(name)` factory function — registry of all adapters, lazy import to avoid loading all deps at once
- [ ] T053 [US5] Add source configuration file in `daas-agent-harness/cli_anything/daas/metadata/sources.yaml` — default config for all 4 sources with enabled/disabled, portal URLs, descriptions
- [ ] T054 [US5] Verify extensibility — write a minimal test adapter (e.g., `DummySource(SourceAdapter)`) in tests, register it, confirm it appears in `list-sources` and `call` works

**Checkpoint**: All 5 user stories complete — full system with extensible adapter pattern

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Tests, documentation, validation

- [ ] T055 [P] Create CLI smoke tests in `daas-agent-harness/tests/test_cli.py` — test `list-sources`, `search`, `describe`, `categories` commands, `--json` flag, REPL invocation (skip if deps missing)
- [ ] T056 [P] Create registry tests in `daas-agent-harness/tests/test_registry.py` — test RegistryService CRUD, search, categories, upsert idempotency
- [ ] T057 [P] Create source adapter tests in `daas-agent-harness/tests/test_sources.py` — test SourceAdapter ABC, DummySource implementation, error handling
- [ ] T058 Run full quickstart.md validation — execute all 7 scenarios, fix any issues
- [ ] T059 Verify no regressions — run `cd akshare-agent-harness && uv run pytest -v` to confirm existing tests still pass
- [ ] T060 Update `CLAUDE.md` — add daas-agent-harness and daas-mcp sections following existing documentation pattern

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001-T005) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational (T006-T012)
- **US2 (Phase 4)**: Depends on Foundational + US1 (T018 — CLI entry point must exist before adding `call`)
- **US3 (Phase 5)**: Depends on Foundational + US2 (needs source adapters with `discover()`)
- **US4 (Phase 6)**: Depends on US3 (needs registry DB populated for MCP to serve)
- **US5 (Phase 7)**: Depends on US2 (needs working adapters to finalize)
- **Polish (Phase 8)**: Depends on all desired user stories

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no other story dependencies
- **US2 (P1)**: Can start after US1 CLI entry point (T018) — needs CLI shell for `call` command. Adapter implementations (T024-T027) can run in parallel with US1 completion
- **US3 (P2)**: Can start after US2 source adapters exist — needs `discover()` on each adapter
- **US4 (P2)**: Can start after US3 registry is built — MCP server serves from registry
- **US5 (P3)**: Can start after US2 adapters work — finalizes and proves pattern

### Within Each User Story

- Models/config before CLI commands
- CLI shell before individual commands
- Stub adapters before full `fetch()` implementations
- Registry persistence before MCP server

### Parallel Opportunities

- **Phase 1**: All 5 tasks [P] — pyproject.toml, setup.py, directory structures, mcp pyproject.toml
- **Phase 2**: T007, T008, T009, T012 all [P] — database.py, base.py, exceptions.py, __init__.py
- **Phase 3 (US1)**: T014, T015, T016, T017 all [P] — all 4 source adapter stubs
- **Phase 4 (US2)**: T025, T026, T027 all [P] — World Bank, CKAN, CNStats fetch implementations
- **Phase 5 (US3)**: T032-T036 sequential (builds on itself)
- **Phase 6 (US4)**: T038, T039, T040 all [P] — MCP models, DB, registry_service
- **Phase 7 (US5)**: T048, T049, T050, T051 all [P] — finalize all 4 adapters
- **Phase 8**: T055, T056, T057 all [P] — all three test files

---

## Parallel Example: User Story 1

```bash
# Launch all 4 source adapter stubs together:
Task: "Create AKShare source adapter stub in daas-agent-harness/cli_anything/daas/sources/akshare_source.py"
Task: "Create World Bank source adapter stub in daas-agent-harness/cli_anything/daas/sources/worldbank_source.py"
Task: "Create CKAN source adapter stub in daas-agent-harness/cli_anything/daas/sources/ckan_source.py"
Task: "Create Chinese Statistics source adapter stub in daas-agent-harness/cli_anything/daas/sources/cnstats_source.py"

# Then CLI entry point (depends on T010 RegistryService):
Task: "Create CLI entry point in daas-agent-harness/cli_anything/daas/cli.py"
```

## Parallel Example: User Story 2

```bash
# Launch all 3 optional-source fetch implementations together:
Task: "Implement fetch() in World Bank source adapter"
Task: "Implement fetch() in CKAN source adapter"
Task: "Implement fetch() in Chinese Statistics source adapter"

# Then router + call command:
Task: "Create SourceRouter in daas-agent-harness/cli_anything/daas/sources/router.py"
Task: "Implement call command in daas-agent-harness/cli_anything/daas/cli.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T012) — **CRITICAL BLOCKER**
3. Complete Phase 3: US1 — Search & Discovery (T013-T023)
4. **STOP and VALIDATE**: `cli-anything-daas search GDP` works
5. Complete Phase 4: US2 — Data Fetching (T024-T031)
6. **STOP and VALIDATE**: `cli-anything-daas call worldbank_gdp country=CN` returns data
7. **MVP READY** — search + fetch work, deploy/demo

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Search/discovery works → Demo
3. Add US2 → Data fetching works → **MVP!**
4. Add US3 → Registry persistence + leader-mcp integration → Demo
5. Add US4 → Skill + MCP server → Claude Code integration
6. Add US5 → Extensibility proven → Full release
7. Polish → Tests + docs → Production ready

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (CLI + discovery) + US2 (fetch + routing)
   - Developer B: US3 (store_registry) → US4 (MCP server)
   - Developer C: US5 (adapter finalization) + Polish (tests)
3. US1+US2 is the critical path for MVP; US3+US4 can overlap

---

## Notes

- [P] tasks = different files, no dependencies — can run concurrently
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Source adapters are namespaced: `akshare_`, `worldbank_`, `ckan_`, `cnstats_` prefixes avoid collisions
- Follow existing akshare harness patterns exactly — same Click CLI style, same RegistryService API, same output formatting
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
