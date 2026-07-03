# cnreport-mcp

MCP server for Chinese A-share annual reports. Thirteen tools across two layers:

| Layer | Tool | What it does |
|---|---|---|
| Company API (edgartools-style) | `get_company` | Resolve ticker / name → company entry |
| | `list_filings` | List CNINFO disclosures by form / category + year |
| | `get_filing` | One announcement's metadata + PDF URL |
| | `get_financials` | Income / balance / cashflow via akshare |
| | `get_section` | `(ticker, year, section)` → section text |
| | `list_report_types` | Browse the CNINFO disclosure category catalog |
| | `get_special_report` | Retrieve a special-type report (招股说明书 / 收购报告书 / …) by category |
| PDF / AI / ES | `list_outline` | Parse 目录 from a report URL or PDF path |
| | `extract_section` | Body text by exact title / regex / ordinal |
| | `ai_extract` | LLM-structured extraction over section text |
| | `index_records` | Bulk index extracted records into ES |
| | `search_reports` | BM25 + filter search with highlights |
| | `delete_index` | Drop `cnreport-{year}` index |

## Typical chain

```python
# 1. Resolve company → 2. find latest annual → 3. pull MD&A → 4. LLM-extract revenue table

co = get_company("600519")
# {"stock_code": "600519", "name": "贵州茅台", "org_id": "gssh0600519", "exchange": "sse", ...}

filings = list_filings("600519", form="年度报告", year=2023, limit=3)
# [{"announcement_id": "1219730876", "pdf_url": "http://static.cninfo.com.cn/.../*.PDF", ...}]

sec = get_section("600519", year=2023, section="管理层讨论与分析")
# {"text": "<full MD&A body>", "pdf_url": "...", "outline_entry": {...}, ...}

records = ai_extract(
    text=sec["text"],
    schema={"type": "object", "properties": {
        "segment": {"type": "string"},
        "revenue_2023": {"type": "string"},
    }, "required": ["segment", "revenue_2023"]},
)
# {"records": [{"segment": "茅台酒", "revenue_2023": "139,989,000,000"}, ...]}
```

## Special report types

CNINFO exposes dozens of disclosure categories beyond the four periodic reports
(招股说明书, 增发, 业绩预告, 收购报告书, 股权激励, …). Browse the catalog, then list or
retrieve by category:

```python
# 1. Browse what's available → 2. list filings of a category → 3. pull a section

catalog = list_report_types()
# {"groups": [{"name": "定期报告", "categories": [...]}, {"name": "融资", ...}, ...], "count": 26}

list_report_types(group="融资")
# {"group": "融资", "categories": [{name: "首发", code: "category_sf_szsh", ...}, ...], "count": 6}

filings = list_filings("600519", category="首发", limit=3)   # 首发 covers 招股说明书
# category accepts a catalog name OR a raw category_* code; mutually exclusive with form.

sec = get_special_report("600519", category="首发", section="募集资金运用")
# {"text": "<section body>", "pdf_url": "...", "outline_entry": {...}, ...}

# Without `section`, the PDF is NOT downloaded — only filing metadata + pdf_url:
meta = get_special_report("600519", category="业绩预告")
```

The category catalog is the data-driven file `cninfo_categories.json` (sourced from
CNINFO's own `history-notice.js` via akshare). **Adding a report type = editing that
JSON** — no code change. Restart the server and the new type appears in
`list_report_types` and is accepted by `list_filings(category=…)` / `get_special_report(…)`.

Skip the company API and pass a PDF URL directly when you already have one:

```python
list_outline(source="https://example.com/600519_2023.pdf")
extract_section(source="...", selector="管理层讨论与分析", company="贵州茅台", year=2023)
```

## Setup

```bash
uv sync                    # installs akshare, pypdf, fastmcp, ...
uv run python server.py    # FastMCP over stdio
```

Self-check (no network):

```bash
uv run python selfcheck.py
```

Tests (offline; bypasses the user's broken logfire pytest plugin):

```bash
uv run --with pytest python -m pytest test_cnreport.py -v -p no:logfire
```

## Configuration

CNINFO and akshare are **keyless**. The other tools need env vars in root `.env`:

| Var | Used by | Required? |
|---|---|---|
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | `ai_extract` | Yes for AI |
| `ES_URL` (+ optional `ES_API_KEY` or `ES_USERNAME`/`ES_PASSWORD`) | `index_records`, `search_reports`, `delete_index` | Yes for ES |
| `DAAS_DATABASE_URL` | provenance writes for `extract_section` | Defaults to `mcp/daas.db` |

## Architecture

- `cninfo_client.py` — single network entry point for CNINFO (`lookup_company`, `query_announcements`, `get_announcement`, `pdf_url`). Three keyless endpoints. Also loads the data-driven category registry (`load_categories`, `resolve_category`).
- `cninfo_categories.json` — CNINFO disclosure category catalog (name → code, grouped). Source of truth for `list_report_types` and the `category` parameter; extensible by JSON edit.
- `financials_client.py` — lazy-imports akshare; server boots even without it (`get_financials` returns an `{error}` instead).
- `cnreport_tools.py` — pure helpers + the company-API wrappers (`list_report_types`, `get_special_report`). Errors return `{"error": ...}`, never raise.
- `server.py` — `@app.tool` registrations; thin pass-through to `cnreport_tools`.
