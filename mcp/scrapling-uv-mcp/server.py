"""scrapling-uv-mcp — Scrapling MCP server via uv-managed Python.

Thin wrapper: scrapling ships its own MCP server. This just invokes it.
"""

from scrapling.core.ai import ScraplingMCPServer

if __name__ == "__main__":
    server = ScraplingMCPServer()
    server.serve(http=False, host="0.0.0.0", port=8000)
