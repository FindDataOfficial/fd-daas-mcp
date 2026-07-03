# hkreport-mcp

Hong Kong stock market financial report MCP — purpose-built FastMCP server for
HKEX-listed companies. Mirrors the `edgartools-mcp` tool surface so agents
already trained on the US filing API generalize.

## Tools

| Tool                       | Purpose                                                |
|----------------------------|--------------------------------------------------------|
| `get_company`              | Resolve a HK-listed company by 5-digit code or name    |
| `list_filings`             | List HKEXnews disclosures (Annual / Interim / ...)     |
| `get_filing`               | Fetch one disclosure (metadata + optional PDF text)    |
| `get_financials`           | Income / balance / cashflow via `akshare` HK reports   |
| `get_disclosure_calendar`  | Upcoming results-announcement and AGM dates            |

## Data sources

- **HKEXnews** (`https://www1.hkexnews.hk/`) — keyless public endpoints for
  instrument search, disclosure list, and PDF documents.
- **akshare** (`stock_financial_hk_report_em`) — normalized HK financial
  statements scraped from EastMoney.

No API key is required. The server starts cleanly with no `HKEX_*` env var.
If `HTTPS_PROXY` / `HTTP_PROXY` is set, outbound HKEXnews calls route through it.

## Run

```bash
uv run --directory mcp/hkreport-mcp python server.py        # stdio MCP server
uv run --directory mcp/hkreport-mcp python selfcheck.py     # offline smoke
uv run --directory mcp/hkreport-mcp python -m pytest test_hkreport.py -v -p no:logfire
```

## Live smoke

```bash
HKREPORT_LIVE=1 uv run --directory mcp/hkreport-mcp python -m pytest -v -p no:logfire
```
