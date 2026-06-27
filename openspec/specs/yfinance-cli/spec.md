## ADDED Requirements

### Requirement: Installable yfinance CLI harness

The system SHALL provide a Click-based CLI harness at `yfinance-agent-harness/` as a PEP 420 namespace package `cli_anything.yfinance`, installable via `setup.py` as the `cli-anything-yfinance` console script, with `python_requires>=3.10` and runtime deps `click`, `pandas`, `yfinance`, `sqlalchemy`.

#### Scenario: Console script is installed

- **WHEN** `uv pip install -e ".[dev,repl]"` is run from `yfinance-agent-harness/`
- **THEN** the `cli-anything-yfinance` console script is available on PATH and dispatches to `cli_anything.yfinance.yfinance_cli:cli`

#### Scenario: Namespace package layout

- **WHEN** the harness package is inspected
- **THEN** it lives under `cli_anything/yfinance/` with no `cli_anything/__init__.py` (PEP 420), mirroring the akshare harness layout

### Requirement: Curated yfinance function registry

The system SHALL ship a curated registry of yfinance callables organized into categories (e.g. price-history, fundamentals, holders, options, calendar, top-level), each entry carrying `command`, `category`, `description`, `source`, `parameters`, and representative `columns`. `Ticker` methods SHALL be registered as `ticker_<method>` (e.g. `ticker_history`, `ticker_info`, `ticker_financials`); top-level functions SHALL be registered by their own name (e.g. `download`, `search`).

#### Scenario: Registry is seeded into SQLite

- **WHEN** `migrate_registry.py` is run
- **THEN** a `metadata/registry.db` is created with `functions` and `function_columns` tables populated from the curated registry, using the two-table design shared with the akshare harness

#### Scenario: Ticker methods are namespaced flat

- **WHEN** the registry is queried for `ticker_history`
- **THEN** an entry exists with `category` (e.g. price-history) and `parameters` including `symbol` plus the method's other parameters

#### Scenario: Top-level functions are registered

- **WHEN** the registry is queried for `download` or `search`
- **THEN** entries exist for both, distinct from any `ticker_*` entry

### Requirement: CLI supports search, info, list, categories, call

The system SHALL expose Click subcommands `search`, `info`, `list`, `categories`, and `call`, behaviorally parallel to `cli-anything-akshare`, all backed by the SQLite registry.

#### Scenario: Search by keyword

- **WHEN** `cli-anything-yfinance search history` is run
- **THEN** it returns matching commands (e.g. `ticker_history`) with their categories

#### Scenario: Info on a known command

- **WHEN** `cli-anything-yfinance info ticker_history` is run
- **THEN** it prints category, description, source, and parameters for `ticker_history`

#### Scenario: List with category filter

- **WHEN** `cli-anything-yfinance list fundamentals` is run
- **THEN** it lists commands whose category matches `fundamentals`

#### Scenario: Categories listing

- **WHEN** `cli-anything-yfinance categories` is run
- **THEN** it lists all categories with function counts, sorted by count descending

#### Scenario: Call executes a live yfinance function

- **WHEN** `cli-anything-yfinance call ticker_history symbol=AAPL period=1mo` is run and `yfinance` is installed
- **THEN** it calls `yf.Ticker("AAPL").history(period="1mo")` and prints the resulting DataFrame

### Requirement: CLI has a REPL mode

The system SHALL provide an interactive REPL as the default subcommand (when no subcommand is given), supporting `list`, `search`, `info`, `categories`, `call`, and `exit`/`help`, mirroring the akshare REPL.

#### Scenario: Default invocation enters REPL

- **WHEN** `cli-anything-yfinance` is run with no subcommand
- **THEN** it enters the REPL prompt

#### Scenario: REPL falls back without prompt_toolkit

- **WHEN** `prompt_toolkit` is not installed
- **THEN** the REPL falls back to a simple input loop instead of erroring

### Requirement: Runner dispatches ticker vs top-level calls

The system SHALL provide a `call_yfinance_function` runner that, given a command name and params, dispatches `ticker_*` commands by constructing `yfinance.Ticker(symbol)` and calling the suffix method, and dispatches other commands as top-level `yfinance.<name>(**params)`.

#### Scenario: Ticker command resolves through Ticker object

- **WHEN** `call_yfinance_function("ticker_info", {"symbol": "AAPL"})` is invoked
- **THEN** the runner constructs `yf.Ticker("AAPL")` and calls `.info`, returning its result

#### Scenario: Top-level command resolves directly

- **WHEN** `call_yfinance_function("search", {"query": "Apple"})` is invoked
- **THEN** the runner calls `yf.search(query="Apple")` directly without constructing a Ticker

#### Scenario: Unknown command errors clearly

- **WHEN** `call_yfinance_function("does_not_exist", {})` is invoked
- **THEN** the runner reports that the command is not found, listing available commands as a hint

### Requirement: Tests skip when yfinance is absent

The system SHALL include pytest tests under `cli_anything/yfinance/tests/` that skip when `yfinance` is not installed, mirroring the akshare test convention.

#### Scenario: Live-call tests are skipped without the library

- **WHEN** tests are run in an environment without `yfinance`
- **THEN** the yfinance-dependent tests are skipped, not failed
