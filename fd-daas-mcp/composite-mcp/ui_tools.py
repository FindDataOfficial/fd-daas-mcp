"""Demo MCP-Apps UI tools for composite-mcp.

Implements the MCP Apps pattern (https://github.com/modelcontextprotocol/ext-apps):
a tool returns ``_meta.ui.resourceUri`` pointing at a ``ui://`` resource, and
the host fetches that resource via ``resources/read`` and renders it inline.

This ships one end-to-end demonstrable tool — ``render_stock_summary`` — so the
dashboard's ``/chat`` page (which renders via ``@mcp-ui/client``'s ``AppRenderer``)
has something to render out of the box. Pure FastMCP: no third-party Python SDK
required (the resource template + ``ToolResult.meta`` cover the whole contract).

Registered as always-present tools (alongside the management tools) so they are
available on every composite regardless of which ``COMPOSITE`` is selected.
"""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.resources import ResourceContent, ResourceResult
from fastmcp.tools.base import ToolResult
from mcp.types import TextContent

# MCP Apps standard MIME type for UI resources.
MCP_APP_MIME = "text/html;profile=mcp-app"

# ponytail: static demo data — a follow-up change wires live akshare data.
_DEMO_PRICES = {
    "AAPL": ("Apple Inc.", 185.50, 1.23),
    "MSFT": ("Microsoft Corp.", 412.80, -0.45),
    "GOOGL": ("Alphabet Inc.", 142.70, 0.88),
    "TSLA": ("Tesla Inc.", 238.40, 2.10),
    "00700": ("Tencent Holdings", 385.20, 0.60),
}


def _stock_summary_html(symbol: str) -> str:
    """Build a small static stock-overview widget as HTML."""
    name, price, change = _DEMO_PRICES.get(
        symbol.upper(), (symbol, 100.00, 0.00)
    )
    sign = "+" if change >= 0 else ""
    color = "#16a34a" if change >= 0 else "#dc2626"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{symbol} summary</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{
      margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
        Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #111827; background: #ffffff;
    }}
    .card {{ padding: 16px; }}
    h2 {{ margin: 0 0 12px; font-size: 16px; font-weight: 600; }}
    .row {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .tile {{
      border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 12px;
      min-width: 120px;
    }}
    .label {{ font-size: 11px; color: #6b7280; text-transform: uppercase;
      letter-spacing: 0.04em; }}
    .value {{ font-size: 18px; font-weight: 600; margin-top: 2px; }}
    .delta {{ font-size: 13px; color: {color}; margin-top: 2px; }}
    .foot {{ margin-top: 12px; font-size: 11px; color: #9ca3af; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>{name} <span style="color:#6b7280;font-weight:400;">({symbol})</span></h2>
    <div class="row">
      <div class="tile">
        <div class="label">Price</div>
        <div class="value">${price:,.2f}</div>
        <div class="delta">{sign}{change:+.2f}</div>
      </div>
      <div class="tile">
        <div class="label">Symbol</div>
        <div class="value">{symbol}</div>
        <div class="delta">demo data</div>
      </div>
    </div>
    <div class="foot">Rendered by composite-mcp via the MCP Apps pattern.</div>
  </div>
</body>
</html>"""


def stock_summary_uri(symbol: str) -> str:
    return f"ui://composite-mcp/stock-summary/{symbol}"


def register(app: FastMCP) -> None:
    """Register the demo UI tool + its resource template on the given app."""

    # Resource template: hosts fetch this via resources/read and pass the HTML
    # to AppRenderer. The {symbol} path param is bound by FastMCP.
    #
    # Returns a ResourceResult with an explicit ResourceContent(mime_type=...)
    # because FastMCP's template convert_result does not forward the
    # decorator's mime_type for plain str returns (it would default to
    # text/plain). Returning ResourceResult bypasses that normalization.
    @app.resource(
        "ui://composite-mcp/stock-summary/{symbol}",
        mime_type=MCP_APP_MIME,
        description="Stock summary UI widget (MCP Apps rawHtml).",
    )
    def stock_summary_resource(symbol: str) -> ResourceResult:
        return ResourceResult(
            [ResourceContent(_stock_summary_html(symbol), mime_type=MCP_APP_MIME)]
        )

    @app.tool()
    def render_stock_summary(symbol: str) -> ToolResult:
        """Render an interactive stock-summary UI widget for a ticker symbol.

        Returns a link to a ``ui://`` resource (in ``_meta.ui.resourceUri``) that
        the host fetches and renders inline. Supported symbols include AAPL,
        MSFT, GOOGL, TSLA, 00700 (others render with placeholder data).
        """
        return ToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Stock summary UI for {symbol}.",
                )
            ],
            meta={"ui": {"resourceUri": stock_summary_uri(symbol)}},
        )
