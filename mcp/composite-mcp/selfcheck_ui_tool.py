"""Self-check for the composite-mcp demo MCP-Apps UI tool.

Hermetic: builds a fresh FastMCP app, registers the demo UI tools, and
exercises the full MCP-Apps round-trip in-process via fastmcp.Client —
no stdio spawn, no DB, no network, no LLM.

Asserts:
  - render_stock_summary is listed in tools/list
  - tools/call returns _meta.ui.resourceUri == ui://composite-mcp/stock-summary/{symbol}
  - resources/read returns mimeType text/html;profile=mcp-app and the HTML body
  - a non-default symbol resolves to its own widget

Run:  uv run --directory mcp/composite-mcp python selfcheck_ui_tool.py
"""
from __future__ import annotations

import asyncio
import sys


def main() -> int:
    from fastmcp import FastMCP, Client
    from ui_tools import register, MCP_APP_MIME

    app = FastMCP(name="composite-mcp-selfcheck")
    register(app)

    async def run() -> None:
        async with Client(app) as client:
            tools = await client.list_tools()
            names = [t.name for t in tools]
            assert "render_stock_summary" in names, f"tool missing from {names}"
            print(f"  tools/list OK ({len(names)} tools, has render_stock_summary)")

            for symbol, expect in [("AAPL", "Apple"), ("TSLA", "Tesla")]:
                r = await client.call_tool(
                    "render_stock_summary", {"symbol": symbol}
                )
                meta = getattr(r, "meta", None) or {}
                uri = meta.get("ui", {}).get("resourceUri")
                assert uri == f"ui://composite-mcp/stock-summary/{symbol}", (
                    f"bad _meta.ui.resourceUri for {symbol}: {uri}"
                )
                print(f"  tools/call {symbol} OK -> {uri}")

                contents = await client.read_resource(uri)
                c = contents[0] if isinstance(contents, list) else contents
                mt = getattr(c, "mimeType", None)
                text = getattr(c, "text", "") or ""
                assert mt == MCP_APP_MIME, f"bad mimeType for {symbol}: {mt!r}"
                assert expect in text, f"{symbol} HTML missing {expect!r}: {text[:80]}"
                assert "<h2>" in text, f"{symbol} HTML missing structure"
                print(
                    f"  resources/read {symbol} OK -> mimeType={mt}, "
                    f"len(html)={len(text)}"
                )

    asyncio.run(run())
    print("\nselfcheck_ui_tool: ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
