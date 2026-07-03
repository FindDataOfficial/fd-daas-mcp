#!/usr/bin/env python3
"""scrapling-uv-mcp — Scrapling fetch tools plus reusable scraper-script management.

Thin wrapper over scrapling's bundled ``ScraplingMCPServer`` (get/fetch/
stealthy_fetch/bulk_*/session/screenshot) with two added tools:

  find_scripts — list reusable scraper scripts in the script dir (name/path/summary)
  run_script   — execute a named scraper script in this venv (path-traversal guarded, timeout)

Entry: python3 server.py             (stdio MCP server)
       python3 server.py --selfcheck (in-process self-check, temp dir, no DB)

Env:
  SCRAPLING_SCRIPTS_DIR     script dir (default: ./scripts/scrapers/, created lazily)
  SCRAPLING_SCRIPT_TIMEOUT  run_script timeout seconds (default 120)
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
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

from scrapling.core.ai import ScraplingMCPServer  # noqa: E402

SERVER_DIR = Path(__file__).resolve().parent
_DEFAULT_SCRIPTS_DIR = SERVER_DIR / "scripts" / "scrapers"


def _scripts_dir() -> Path:
    """Resolve and lazily create the scraper script directory."""
    raw = os.environ.get("SCRAPLING_SCRIPTS_DIR") or str(_DEFAULT_SCRIPTS_DIR)
    d = Path(raw).expanduser().resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _script_timeout() -> int:
    try:
        return max(1, int(os.environ.get("SCRAPLING_SCRIPT_TIMEOUT", "120")))
    except (TypeError, ValueError):
        return 120


def _summary(path: Path) -> str:
    """One-line summary: first line of the module docstring, else first `#` comment, else ''."""
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        doc = ast.get_docstring(ast.parse(text))
        if doc:
            return doc.strip().splitlines()[0]
    except Exception:
        pass
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
    return ""


class ScraplingExtractServer(ScraplingMCPServer):
    """ScraplingMCPServer + find_scripts/run_script."""

    def find_scripts(self) -> dict:
        """List every reusable scraper script in the script directory.

        Returns ``{"scripts": [{name, path, summary}], "count": N}``. Never executes scripts.
        """
        base = _scripts_dir()
        scripts = []
        for p in sorted(base.glob("*.py")):
            scripts.append({"name": p.stem, "path": str(p), "summary": _summary(p)})
        return {"scripts": scripts, "count": len(scripts)}

    def run_script(self, name: str, args: list[str] | None = None) -> dict:
        """Run a scraper script from the script directory in this venv.

        ``name`` is the script stem (``<name>.py``); optional ``args`` are forwarded.
        Returns ``{"returncode", "stdout", "stderr"}``. Unknown scripts and any name
        that escapes the script directory (e.g. ``../x``) are rejected without execution.
        """
        if not name:
            return {"error": "name is required"}
        base = _scripts_dir().resolve()
        target = (base / f"{name}.py").resolve()
        # ponytail: flat dir — target must sit directly under base; this also blocks
        # path traversal (../x, foo/bar) and symlink escapes via .resolve().
        if target.parent != base:
            return {"error": f"Invalid script name (rejected): {name!r}"}
        if not target.is_file():
            return {"error": f"Script not found: {name}"}
        try:
            cp = subprocess.run(
                [sys.executable, str(target), *(args or [])],
                cwd=str(SERVER_DIR),
                capture_output=True,
                text=True,
                timeout=_script_timeout(),
            )
        except subprocess.TimeoutExpired as e:
            return {
                "returncode": -1,
                "timeout": True,
                "stdout": e.stdout or "",
                "stderr": (e.stderr or "") + f"\nTimeout after {_script_timeout()}s",
            }
        return {"returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}

    def serve(self, http: bool = False, host: str = "0.0.0.0", port: int = 8000):
        """Serve the MCP server: scrapling's fetch tools + our two script tools."""
        from mcp.server.fastmcp import FastMCP

        server = FastMCP(name="Scrapling", host=host, port=port)
        # Session management tools
        server.add_tool(self.open_session, title="open_session", structured_output=True)
        server.add_tool(self.close_session, title="close_session", structured_output=True)
        server.add_tool(self.list_sessions, title="list_sessions", structured_output=True)
        # HTTP tools
        server.add_tool(self.get, title="get", description=self.get.__doc__, structured_output=True)
        server.add_tool(self.bulk_get, title="bulk_get", description=self.bulk_get.__doc__, structured_output=True)
        # Dynamic browser tools
        server.add_tool(self.fetch, title="fetch", description=self.fetch.__doc__, structured_output=True)
        server.add_tool(self.bulk_fetch, title="bulk_fetch", description=self.bulk_fetch.__doc__, structured_output=True)
        # Stealthy browser tools
        server.add_tool(self.stealthy_fetch, title="stealthy_fetch", description=self.stealthy_fetch.__doc__, structured_output=True)
        server.add_tool(self.bulk_stealthy_fetch, title="bulk_stealthy_fetch", description=self.bulk_stealthy_fetch.__doc__, structured_output=True)
        # Screenshot tool
        server.add_tool(self.screenshot, title="screenshot", description=self.screenshot.__doc__)
        # Script-management tools (this change)
        server.add_tool(self.find_scripts, title="find_scripts", description=self.find_scripts.__doc__)
        server.add_tool(self.run_script, title="run_script", description=self.run_script.__doc__)
        # ponytail: the lines above duplicate scrapling's tool list (its serve() builds
        # and runs internally with no add-tool hook). If scrapling changes its tools,
        # update this list; the selfcheck asserts find_scripts/run_script are present.
        server.run(transport="stdio" if not http else "streamable-http")


def _selfcheck() -> int:
    """In-process self-check on a temp script dir. Never touches daas.db."""
    import tempfile

    failures = []

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["SCRAPLING_SCRIPTS_DIR"] = tmp
        s = ScraplingExtractServer()

        # write a tiny scraper with a module docstring
        (Path(tmp) / "echo.py").write_text(
            '"""echo scraper — prints argv as JSON."""\n'
            "import json, sys\n"
            'print(json.dumps({"args": sys.argv[1:]}))\n',
            encoding="utf-8",
        )

        # find_scripts lists it with a non-empty summary
        found = s.find_scripts()
        names = [x["name"] for x in found["scripts"]]
        if "echo" not in names:
            failures.append(f"find_scripts did not list echo: {names}")
        else:
            echo = next(x for x in found["scripts"] if x["name"] == "echo")
            if not echo["summary"]:
                failures.append("echo summary empty")

        # run_script success
        r = s.run_script("echo", ["hello"])
        if r.get("returncode") != 0:
            failures.append(f"echo run failed: {r}")
        elif "hello" not in r.get("stdout", ""):
            failures.append(f"echo stdout missing arg: {r}")

        # unknown script
        r = s.run_script("missing")
        if "error" not in r:
            failures.append(f"missing script should error: {r}")

        # path traversal rejected (no execution, no file access outside dir)
        r = s.run_script("../etc/passwd")
        if "error" not in r:
            failures.append(f"traversal should be rejected: {r}")
        r = s.run_script("foo/bar")
        if "error" not in r:
            failures.append(f"nested name should be rejected: {r}")

    if failures:
        print("SELFCHECK FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("SELFCHECK OK: find_scripts + run_script (list, run, unknown, traversal-guard) pass")
    return 0


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        raise SystemExit(_selfcheck())
    ScraplingExtractServer().serve(http=False, host="0.0.0.0", port=8000)
