## ADDED Requirements

### Requirement: FastMCP yfinance server with five tools

The system SHALL provide a FastMCP server at `mcp/yfinance-mcp/server.py` using stdio transport, exposing five tools: `search_functions`, `get_function_info`, `list_categories`, `list_functions`, and `call_yfinance_function`, mirroring the `mcp/akshare-mcp/server.py` pattern.

#### Scenario: Server starts and registers tools

- **WHEN** the server is started with `python3 server.py`
- **THEN** all five tools are registered and callable over stdio

#### Scenario: Server follows existing MCP pattern

- **WHEN** the server is started
- **THEN** it uses FastMCP with stdio transport, matching the pattern of `mcp/akshare-mcp/server.py`

### Requirement: Registry-query tools read the harness registry

The `search_functions`, `get_function_info`, `list_categories`, and `list_functions` tools SHALL query the `cli_anything.yfinance` registry by importing it with the harness root on `sys.path`, exactly as `akshare-mcp` imports `cli_anything.akshare`.

#### Scenario: search_functions matches name, category, description

- **WHEN** `search_functions(query="history")` is called
- **THEN** it returns yfinance commands whose name/category/description match, with name, category, and description fields

#### Scenario: get_function_info returns full metadata

- **WHEN** `get_function_info(name="ticker_history")` is called
- **THEN** it returns parameters, columns, category, description, and source for that command

#### Scenario: get_function_info on unknown command

- **WHEN** `get_function_info(name="nope")` is called
- **THEN** it returns an `error` field indicating the command was not found

#### Scenario: list_functions filters by category substring

- **WHEN** `list_functions(category="fundamentals")` is called
- **THEN** it returns only commands whose category matches the substring, capped by `limit`

#### Scenario: list_categories returns counts

- **WHEN** `list_categories()` is called
- **THEN** it returns categories sorted by function count descending

### Requirement: call_yfinance_function executes live yfinance calls

The `call_yfinance_function(name, params_json)` tool SHALL execute the real yfinance library and return results as JSON-serializable data, dispatching `ticker_*` commands through `yfinance.Ticker(symbol)` and top-level commands through `yfinance.<name>(**params)`.

#### Scenario: Live ticker call returns serialized data

- **WHEN** `call_yfinance_function(name="ticker_history", params_json='{"symbol":"AAPL","period":"1mo"}')` is called and yfinance is installed
- **THEN** it returns a `dataframe`-typed result with `shape`, `columns`, and `data` records

#### Scenario: Missing yfinance returns a clear error

- **WHEN** `call_yfinance_function` is called and `yfinance` is not importable
- **THEN** it returns an `error` field with an install hint

#### Scenario: Invalid params_json returns an error

- **WHEN** `call_yfinance_function(name="ticker_history", params_json='{bad json')` is called
- **THEN** it returns an `error` field describing the invalid JSON

#### Scenario: Parameter errors surface the expected signature

- **WHEN** a call raises a `TypeError` due to wrong parameters
- **THEN** the tool returns an `error` field plus `expected_params` listing the function signature

### Requirement: Server packaged and registered in .mcp.json

The system SHALL ship `mcp/yfinance-mcp/pyproject.toml` (deps `fastmcp`, `yfinance`, `pandas`, `sqlalchemy`, `click`) and `.env`/`.env.example` with `YFINANCE_DATABASE_URL`, and root `.mcp.json` SHALL register `yfinance-mcp` using the `uv run --directory <path> python server.py` invocation.

#### Scenario: pyproject declares dependencies

- **WHEN** `mcp/yfinance-mcp/pyproject.toml` is inspected
- **THEN** it declares `fastmcp>=2.0`, `yfinance`, `pandas>=1.0`, `sqlalchemy>=1.4`, and `click>=8.0`, with `requires-python>=3.10`

#### Scenario: .mcp.json registers the server

- **WHEN** root `.mcp.json` is inspected
- **THEN** it contains a `yfinance-mcp` entry with `type: stdio` and a `uv run --directory ... python server.py` command, parallel to the `cron-mcp` entry

#### Scenario: dotenv loads root env first

- **WHEN** the server starts
- **THEN** it loads the root `.env` before its own `.env` with `override=True`, matching the unified-env convention used by the other MCPs
