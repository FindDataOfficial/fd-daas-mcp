"""Consolidated FastMCP server - registers every tool from the registry under
the ``<group>_<tool>`` namespace and runs over stdio.

Entry: ``python -m cli_anything.fd_daas_mcp.server`` (the ``.mcp.json`` launch).
The ``fd-daas-mcp`` console script (``cli:cli``) is the CLI; both consume the
same :mod:`registry` so they cannot drift.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

from cli_anything.fd_daas_mcp import registry

REPO = Path(__file__).resolve().parents[3]  # repo root
load_dotenv(REPO / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("fd-daas-mcp")

app = FastMCP(name="fd-daas-mcp")

_tools = registry.build()
for _group, _name, _func in _tools:
    try:
        app.tool(name=registry.namespaced(_group, _name))(_func)
    except Exception as e:  # noqa: BLE001 - record + keep going; surfaced via report
        registry.note_failed(_group, _name, f"{type(e).__name__}: {e}")
        logger.warning("failed to register %s_%s: %s", _group, _name, e)

_report = registry.build_report()
logger.info("fd-daas-mcp server: registered=%d failed=%d skipped_optional=%d",
            len(_report["registered"]), len(_report["failed"]),
            len(_report["skipped_optional"]))


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
