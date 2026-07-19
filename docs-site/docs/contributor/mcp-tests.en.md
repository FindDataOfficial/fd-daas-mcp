# MCP Test Suite

The `fd-daas-mcp` server ships an offline pytest suite and a selfcheck. Run them
before/after any change to the server or a group.

## Run the tests

```bash
fd-daas-mcp/.venv/bin/python -m pytest fd-daas-mcp/tests
```

The suite is offline - it does not hit the network. It covers the registry
build, per-group tool wiring, and the consolidation layer.

## Selfcheck (offline invariants)

```bash
fd-daas-mcp/.venv/bin/python -m fd_daas_mcp.selfcheck
```

`selfcheck.py` runs `run_invariants()` - confirms the server is wired correctly
(registry harvests tools from each `<group>-mcp/`, server and CLI surfaces
match, etc.).

## Launch the server (manual)

```bash
fd-daas-mcp/bin/fd-daas-mcp-server
```

`.mcp.json` points `command` at this script - a self-locating POSIX shell that
sets `PYTHONPATH` and execs `.venv/bin/python -m fd_daas_mcp.server`.

## Layout

```
fd-daas-mcp/
  daas/fd_daas_mcp/    # server.py / registry.py / cli.py / selfcheck.py
  <group>-mcp/         # alerts/cron/composite/daas/dashboard/leader/pdf/research
  bin/fd-daas-mcp-server
  tests/               # offline pytest suite
  pyproject.toml
```

## Adding an MCP tool

1. Add the tool in its group package (`fd-daas-mcp/<group>-mcp/`).
2. `registry.build()` AST-harvests it automatically (per-group `sys.modules`
   isolation) - it shows up as `<group>_<tool>` on both server and CLI.
3. Run the tests + selfcheck.
4. Add a line to [MCP Tools -> Tool Groups](../mcp/groups.md) if it's
   user-facing.
