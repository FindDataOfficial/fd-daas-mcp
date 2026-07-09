## ADDED Requirements

### Requirement: Launch shim pins the upstream mcp_massive package and execs its server

The system SHALL provide `mcp/massive-mcp/` containing a `pyproject.toml` that pins `mcp_massive @ git+https://github.com/massive-com/mcp_massive@v0.10.0` as a dependency (with `python-dotenv`) and declares `requires-python = ">=3.12"` (the upstream package's floor), and a `server.py` that loads the unified root `.env` and then replaces its own process with the upstream `mcp_massive` console script via `os.execvp("mcp_massive", ["mcp_massive"])`. The directory SHALL NOT contain a hand-written FastMCP server that re-exposes the upstream's tools — `mcp_massive` is already a complete MCP server and is delegated to verbatim.

#### Scenario: pyproject pins the upstream version and Python floor

- **WHEN** `mcp/massive-mcp/pyproject.toml` is read
- **THEN** its dependencies include `mcp_massive @ git+https://github.com/massive-com/mcp_massive@v0.10.0`
- **AND** `requires-python` is `>=3.12`
- **AND** `python-dotenv` is declared so the shim can load the root `.env`

#### Scenario: Shim execs the upstream server, inheriting stdio and env

- **WHEN** `uv run --directory mcp/massive-mcp python server.py` is launched with `MASSIVE_API_KEY` present in the environment and stdio connected
- **THEN** the process replaces itself with the `mcp_massive` console script
- **AND** the replacing process inherits the same stdio streams and the same environment (so `MASSIVE_API_KEY` is visible to `mcp_massive`)
- **AND** the replacing process speaks the MCP stdio protocol

### Requirement: MASSIVE_API_KEY is required and loaded from the unified root .env

The shim SHALL load `.env` from the repository root (via `load_dotenv`) before exec'ing the upstream server, so `MASSIVE_API_KEY` enters the process environment from the project's single secrets source. The shim SHALL fail fast with a clear stderr message and a non-zero exit if `MASSIVE_API_KEY` is unset or empty, without launching the upstream server. The key SHALL NOT be stored in `leader_upstreams.env_json`, in `mcp/daas.db`, or in any committed file.

#### Scenario: Missing key fails fast with a clear message

- **WHEN** the shim is launched with `MASSIVE_API_KEY` unset and empty
- **THEN** it writes a message naming `MASSIVE_API_KEY` and pointing to the root `.env`
- **AND** it exits with a non-zero status
- **AND** it does NOT exec `mcp_massive`

#### Scenario: Key present in root .env flows to the upstream server

- **GIVEN** the root `.env` contains `MASSIVE_API_KEY=<value>`
- **WHEN** the shim is launched via `uv run --directory mcp/massive-mcp python server.py`
- **THEN** `MASSIVE_API_KEY` is present in the environment of the replacing `mcp_massive` process
- **AND** the upstream server starts without a key-missing error

### Requirement: massive registered as a leader_upstreams row with env inheritance

The system SHALL register a `massive` row in the `leader_upstreams` table with `transport="stdio"`, `command="uv"`, `args=["run","--directory","<repo>/mcp/massive-mcp","python","server.py"]`, `env=NULL` (so the spawned subprocess inherits the leader-mcp parent environment, where `MASSIVE_API_KEY` already lives after leader-mcp's own `load_dotenv`), `enabled=True`, and a description naming the three upstream tools. The row SHALL be created by an idempotent seeder `mcp/leader-mcp/seed_massive_upstream.py` (upsert on `name="massive"`), NOT by adding an entry to `.mcp.json`.

#### Scenario: Seeder upserts the massive upstream row

- **WHEN** `uv run --directory mcp/leader-mcp python seed_massive_upstream.py` is run
- **THEN** a row with `name="massive"` exists in `leader_upstreams` with `enabled=1`
- **AND** `env_json` is NULL
- **AND** `args_json` contains `run`, `--directory`, `python`, and `server.py`
- **AND** `list_data_mcps()` returns an entry for `massive`

#### Scenario: Re-running the seeder is a no-op

- **GIVEN** the seeder has run successfully once
- **WHEN** the seeder is run a second time
- **THEN** exactly one row with `name="massive"` remains in `leader_upstreams`
- **AND** the exit status is 0

#### Scenario: --unseed removes the massive upstream row

- **GIVEN** the `massive` row exists in `leader_upstreams`
- **WHEN** `seed_massive_upstream.py --unseed` is run
- **THEN** the `massive` row is deleted
- **AND** `list_data_mcps(include_disabled=True)` no longer returns `massive`

### Requirement: Three composable tools reachable through the leader-mcp gateway

Once the `massive` upstream is registered and `MASSIVE_API_KEY` is set, `list_data_mcp_tools(server="massive")` SHALL return at least the three tools published by `mcp_massive` v0.10.0 — `search_endpoints`, `call_api`, and `query_data` — and `call_data_mcp(server="massive", tool=<tool>, arguments=<json>)` SHALL invoke each of them and return the upstream's raw result, with the subprocess torn down after the call.

#### Scenario: list_data_mcp_tools enumerates the three upstream tools

- **WHEN** `list_data_mcp_tools(server="massive")` is called and `MASSIVE_API_KEY` is set
- **THEN** the returned tool list includes `search_endpoints`, `call_api`, and `query_data`

#### Scenario: call_data_mcp dispatches to an upstream tool

- **WHEN** `call_data_mcp(server="massive", tool="search_endpoints", arguments='{"query":"aapl stock price"}')` is called
- **THEN** the system connects to the `massive` upstream, invokes `search_endpoints` with those arguments
- **AND** returns the same JSON result `mcp_massive` would return directly
- **AND** terminates the subprocess after the call
