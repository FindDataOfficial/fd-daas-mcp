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
        app.add_tool(_func, name=registry.namespaced(_group, _name))
    except Exception as e:  # noqa: BLE001
        logger.warning("failed to register %s_%s: %s", _group, _name, e)

logger.info("fd-daas-mcp server: registered %d tools", len(_tools))


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
