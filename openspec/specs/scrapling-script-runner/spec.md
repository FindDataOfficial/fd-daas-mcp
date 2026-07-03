# scrapling-script-runner Specification

## Purpose
TBD - created by archiving change add-scrapling-extract-skill-with-cron. Update Purpose after archive.
## Requirements
### Requirement: Script directory resolution
The scrapling-uv-mcp server SHALL resolve a single script directory from the `SCRAPLING_SCRIPTS_DIR` environment variable, defaulting to `mcp/scrapling-uv-mcp/scripts/scrapers/` when unset. The server SHALL create the directory (including parents) lazily when `find_scripts` or `run_script` is invoked and the directory does not yet exist.

#### Scenario: default directory is used when env unset
- **WHEN** `SCRAPLING_SCRIPTS_DIR` is not set and a client calls `find_scripts`
- **THEN** the server scans `mcp/scrapling-uv-mcp/scripts/scrapers/`, creating it if absent, and returns the scripts found there

#### Scenario: env override is honored
- **WHEN** `SCRAPLING_SCRIPTS_DIR` is set to an absolute path
- **THEN** the server scans that path instead of the default, creating it if absent

### Requirement: Discover scrapling scripts
The server SHALL expose a `find_scripts` tool that lists every `*.py` file in the resolved script directory. For each file it SHALL return the script name (file stem), its absolute path, and a one-line summary parsed from the module docstring or, failing that, the first `#` comment line; if neither is present, the summary SHALL be empty. `find_scripts` SHALL NOT execute any script.

#### Scenario: list scripts with summaries
- **WHEN** the script directory contains `news.py` (with a module docstring) and `prices.py` (with only a `#` comment)
- **THEN** `find_scripts` returns both entries, each with `name`, `path`, and a non-empty `summary` derived from the docstring/comment respectively

#### Scenario: empty directory
- **WHEN** the script directory exists but contains no `*.py` files
- **THEN** `find_scripts` returns an empty list

#### Scenario: directory auto-created
- **WHEN** the script directory does not exist and a client calls `find_scripts`
- **THEN** the server creates the directory and returns an empty list

### Requirement: Run a scrapling script
The server SHALL expose a `run_script` tool that executes a named script from the resolved directory in the server's own Python environment, forwarding optional positional `args`. The tool SHALL resolve the target as `<script_dir>/<name>.py` and SHALL reject any `name` containing a path separator or `..` (no path traversal). Execution SHALL use the server's interpreter with the MCP directory as the working directory, capture stdout and stderr as text, enforce a timeout (default 120s, overridable via `SCRAPLING_SCRIPT_TIMEOUT`), and return the exit code, stdout, and stderr.

#### Scenario: successful run
- **WHEN** a client calls `run_script` with `name="news"` and the script exists and exits 0, printing JSON to stdout
- **THEN** the tool returns `returncode=0`, the captured stdout (including the JSON), and stderr

#### Scenario: unknown script
- **WHEN** a client calls `run_script` with `name="missing"` and no `missing.py` exists
- **THEN** the tool returns an error indicating the script was not found, without executing anything

#### Scenario: path traversal rejected
- **WHEN** a client calls `run_script` with `name="../etc/passwd"` or any name containing `/` or `..`
- **THEN** the tool rejects the name and does not resolve or execute a path outside the script directory

#### Scenario: timeout enforced
- **WHEN** a script runs longer than the configured timeout
- **THEN** the tool terminates the process and returns an error/`returncode` indicating a timeout, with any stdout/stderr captured up to that point

#### Scenario: arguments forwarded
- **WHEN** a client calls `run_script` with `name="news"` and `args=["--out", "data.json"]`
- **THEN** the script is invoked as `<interpreter> <dir>/news.py --out data.json`

