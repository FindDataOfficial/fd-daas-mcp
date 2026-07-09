"""
Massive.com MCP Server — launch shim over the upstream `mcp_massive` package.

`mcp_massive` (github.com/massive-com/mcp_massive) is a *pre-built* MCP server
distributed as a console script (`mcp_massive` → `mcp_massive:main`). It is NOT
a Python library to wrap, so this file does not re-expose its tools via FastMCP
— that would be pointless indirection over a server that already speaks MCP.
Instead this shim:

  1. loads the unified root `.env` (so MASSIVE_API_KEY enters the process env),
  2. fails fast with a clear message if MASSIVE_API_KEY is missing,
  3. replaces its own process with the upstream `mcp_massive` server via
     os.execvp (inheriting stdio + env, so the key flows through).

Launched uniformly with the other data-fetch MCPs:
    uv run --directory mcp/massive-mcp python server.py

The `massive` leader_upstreams row carries env=NULL, so leader-mcp's
build_client lets the subprocess inherit the parent env (where the key already
lives after leader-mcp's own load_dotenv). The dotenv load below is a
belt-and-suspenders fallback for standalone runs.

Self-check (offline, no network, no real exec):
    python server.py --selfcheck
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Unified env: root .env first, then per-MCP .env with override=True
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass


def _key() -> str:
    return os.environ.get("MASSIVE_API_KEY", "").strip()


def _missing_key_error() -> int:
    sys.stderr.write(
        "massive-mcp: MASSIVE_API_KEY is not set. "
        "Add MASSIVE_API_KEY=<your key> to the repo-root .env "
        "(get a key from https://massive.com).\n"
    )
    return 1


def _exec_server() -> int:
    """Replace this process with the upstream mcp_massive server.

    execvp searches PATH; under `uv run --directory` the venv bin (which holds
    the mcp_massive console script declared in pyproject.toml) is on PATH.
    """
    os.execvp("mcp_massive", ["mcp_massive"])
    return 0  # unreachable — exec replaces the process


def _run() -> int:
    """Decision branch used by both main() and the self-check."""
    if not _key():
        return _missing_key_error()
    return _exec_server()


def _selfcheck() -> int:
    """Offline check of the key-guard + exec logic. No network, no real exec."""
    real_execvp = os.execvp
    called: dict = {}

    def _fake_execvp(name, argv):
        called["name"] = name
        called["argv"] = list(argv)
        raise SystemExit(0)  # stand in for "exec succeeded"

    saved_key = os.environ.get("MASSIVE_API_KEY")
    os.execvp = _fake_execvp  # type: ignore[assignment]
    try:
        # 1. Missing key → guard fires, returns 1, execvp NOT called.
        os.environ.pop("MASSIVE_API_KEY", None)
        called.clear()
        rc = _run()
        assert rc == 1, f"missing-key guard should return 1, got {rc}"
        assert called == {}, f"execvp must not fire when key is missing: {called}"

        # 2. Key present → execvp fires with the mcp_massive console script.
        os.environ["MASSIVE_API_KEY"] = "dummy-key-for-selfcheck"
        called.clear()
        try:
            _run()
        except SystemExit:
            pass
        assert called == {"name": "mcp_massive", "argv": ["mcp_massive"]}, called
    finally:
        os.execvp = real_execvp  # type: ignore[assignment]
        if saved_key is None:
            os.environ.pop("MASSIVE_API_KEY", None)
        else:
            os.environ["MASSIVE_API_KEY"] = saved_key

    print("selfcheck OK")
    return 0


def main() -> int:
    if "--selfcheck" in sys.argv:
        return _selfcheck()
    return _run()


if __name__ == "__main__":
    raise SystemExit(main())
