"""
MCP Server for cnreport-mcp — Chinese annual report extraction + AI processing
+ Elasticsearch store/search.

Tools:
  list_outline     — fetch a report and return its 目录 outline
  extract_section  — extract one section's body text by selector
  ai_extract       — LLM structured extraction over section text
  index_records    — bulk-index records into cnreport-{year}
  search_reports   — full-text + filtered search over indexed content
  delete_index     — drop a cnreport-{year} index

Entry: python3 server.py  (FastMCP, stdio transport)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Unified env: root .env first, then per-MCP .env with override=True
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

# make mcp/models importable
_MODELS = Path(__file__).resolve().parent.parent / "models"
if str(_MODELS) not in sys.path:
    sys.path.insert(0, str(_MODELS))

from fastmcp import FastMCP  # noqa: E402

import cnreport_tools as T  # noqa: E402
from cnreport_database import get_db, make_report_id  # noqa: E402

logger = logging.getLogger("cnreport-mcp")
app = FastMCP(name="cnreport-mcp")

_DEFAULT_MAX_CHARS = 12000
_MAX_SIZE = 50


# ── outline extraction tools ────────────────────────────────────


@app.tool
def list_outline(source: str, fetcher: str = "uv") -> dict:
    """Fetch a Chinese annual report and return its 目录 outline.

    Args:
        source: report URL or local file path (.html/.pdf/.txt).
        fetcher: reserved (v1 uses httpx/pypdf); default "uv".
    """
    try:
        text = T.fetch_source(source, fetcher)
    except Exception as e:
        return {"error": f"fetch failed: {type(e).__name__}: {e}"}
    outline = T.parse_outline(text)
    return {"source": source, "char_count": len(text), "sections": outline}


@app.tool
def extract_section(
    source: str,
    selector: str,
    company: Optional[str] = None,
    stock_code: Optional[str] = None,
    year: Optional[int] = None,
    fetcher: str = "uv",
) -> dict:
    """Extract one section's body text by selector.

    Args:
        source: report URL or local file path.
        selector: exact section title, regex, or 1-based ordinal.
        company/stock_code/year: optional provenance metadata, persisted with the report.
        fetcher: reserved (v1 uses httpx/pypdf).
    """
    try:
        text = T.fetch_source(source, fetcher)
    except Exception as e:
        return {"error": f"fetch failed: {type(e).__name__}: {e}"}
    outline = T.parse_outline(text)
    entry = T.resolve_selector(outline, selector)
    if entry is None:
        return {
            "error": "no section matched selector",
            "available": [e["title"] for e in outline],
        }
    body = T.extract_section_text(text, outline, entry)

    report_id = make_report_id(source, company, year)
    db = get_db()
    db.upsert_document(report_id, source, company, stock_code, year, parse_status="ok")
    db.upsert_section(report_id, entry["ordinal"], entry["level"], entry["title"], len(body))

    return {
        "report_id": report_id,
        "section": entry,
        "char_count": len(body),
        "text": body,
    }


# ── AI processing tool ──────────────────────────────────────────


@app.tool
def ai_extract(
    text: str,
    schema: dict,
    prompt: Optional[str] = None,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> dict:
    """Run LLM structured extraction over report section text.

    Args:
        text: section body text.
        schema: JSON Schema the output must conform to (a record or array of records).
        prompt: optional extra instructions.
        max_chars: truncate input to this many chars (default 12000).
    """
    cfg = T.llm_config()
    if not cfg["api_key"]:
        return {"error": "LLM_API_KEY is not configured"}

    truncated = len(text) > max_chars
    snippet = text[:max_chars]
    system = (
        "You extract structured data from Chinese annual report text. "
        "Return ONLY a JSON object with a 'records' array matching the given schema. "
        "Do not include any prose."
    )
    if prompt:
        system += f" {prompt}"
    user = json.dumps({"schema": schema, "text": snippet}, ensure_ascii=False)

    def _attempt(extra: str = "") -> tuple[Optional[list], Optional[str]]:
        try:
            content = T.call_llm_json(system + extra, user)
            data = json.loads(content)
            records = data.get("records") if isinstance(data, dict) else data
            if not isinstance(records, list):
                return None, "model did not return a records array"
            err = T.validate_against_schema(records, _array_schema(schema))
            if err:
                return None, err
            return records, None
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"

    records, err = _attempt()
    if records is None and err is not None:
        records, err = _attempt(" Your previous output was invalid; fix it and return strict JSON conforming to the schema.")
    if records is None:
        return {"error": "extraction failed", "detail": err, "truncated": truncated}

    return {"records": records, "count": len(records), "truncated": truncated}


def _array_schema(item_schema: dict) -> dict:
    """Wrap a record schema into an array schema for validation."""
    return {"type": "array", "items": item_schema}


# ── Elasticsearch store tool ────────────────────────────────────


@app.tool
def index_records(
    records: list,
    year: int,
    report_id: str,
    section_id: str,
    company: Optional[str] = None,
    stock_code: Optional[str] = None,
    section: Optional[str] = None,
) -> dict:
    """Bulk-index extracted records into cnreport-{year}.

    Args:
        records: list of record dicts (e.g. from ai_extract).
        year: report year → determines the index name.
        report_id/section_id: provenance; form the document _id.
        company/stock_code/section: optional filters stored on each doc.
    """
    try:
        es = T.es_client()
    except Exception as e:
        return {"error": f"ES unavailable: {e}"}

    try:
        name, mapping = T.ensure_index(es, year)
    except Exception as e:
        return {"error": f"index create failed: {e}"}

    now = datetime.now(timezone.utc).isoformat()
    docs = T.records_to_docs(records, report_id, section_id)
    actions = []
    for d in docs:
        doc = {
            "report_id": d["report_id"],
            "section_id": d["section_id"],
            "section": section or d["section"],
            "company": company,
            "stock_code": stock_code,
            "year": year,
            "text": d["text"],
            "fields": d["fields"],
            "indexed_at": now,
        }
        actions.append({"index": {"_index": name, "_id": d["_id"]}})
        actions.append(doc)

    succeeded = failed = 0
    if actions:
        try:
            resp = es.bulk(operations=actions, refresh=True)
            for item in resp.get("items", []):
                if "error" in item.get("index", {}):
                    failed += 1
                else:
                    succeeded += 1
        except Exception as e:
            return {"error": f"bulk failed: {e}", "index": name}

    # refresh doc_count from the index
    try:
        count = es.count(index=name)["count"]
    except Exception:
        count = succeeded

    get_db().upsert_es_index(name, count, T.mapping_hash(mapping))
    return {
        "index": name,
        "succeeded": succeeded,
        "failed": failed,
        "doc_count": count,
    }


# ── Elasticsearch search tool ───────────────────────────────────


@app.tool
def search_reports(
    query: str,
    year: Optional[int] = None,
    company: Optional[str] = None,
    stock_code: Optional[str] = None,
    section: Optional[str] = None,
    from_: int = 0,
    size: int = 25,
) -> dict:
    """Full-text + filtered search over cnreport indices with highlights.

    Args:
        query: free-text query (matches the indexed text/fields).
        year: restrict to cnreport-{year}; None searches all cnreport-*.
        company/stock_code/section: optional term filters.
        from_/size: pagination; size capped at 50.
    """
    size = max(1, min(size, _MAX_SIZE))
    try:
        es = T.es_client()
    except Exception as e:
        return {"error": f"ES unavailable: {e}"}

    index = T.index_name_for(year) if year else "cnreport-*"
    filters = []
    if company:
        filters.append({"term": {"company": company}})
    if stock_code:
        filters.append({"term": {"stock_code": stock_code}})
    if section:
        filters.append({"term": {"section": section}})

    must = [{"match": {"text": query}}] if query else [{"match_all": {}}]
    body = {
        "from": from_,
        "size": size,
        "query": {"bool": {"must": must, "filter": filters}} if filters else {"bool": {"must": must}},
        "highlight": {"fields": {"text": {}}},
    }
    try:
        resp = es.search(index=index, body=body)
    except Exception as e:
        return {"error": f"search failed: {e}"}

    hits = []
    for h in resp["hits"]["hits"]:
        hits.append(
            {
                "id": h["_id"],
                "score": h.get("_score"),
                "source": h["_source"],
                "highlight": h.get("highlight", {}).get("text", []),
            }
        )
    return {
        "total": resp["hits"]["total"]["value"],
        "returned": len(hits),
        "hits": hits,
    }


@app.tool
def delete_index(year: int, confirm: bool = False) -> dict:
    """Drop the cnreport-{year} Elasticsearch index and its metadata row.

    Args:
        year: which index year to delete.
        confirm: must be True to actually delete.
    """
    if not confirm:
        return {"error": "pass confirm=true to delete"}
    try:
        es = T.es_client()
    except Exception as e:
        return {"error": f"ES unavailable: {e}"}
    name = T.index_name_for(year)
    try:
        es.indices.delete(index=name)
    except Exception as e:
        return {"error": f"delete failed: {e}"}
    get_db().remove_es_index(name)
    return {"deleted": name}


# ── company API tools (edgartools-style) ────────────────────────


@app.tool
def get_company(ticker_or_name: str) -> dict:
    """Resolve a CN-A-share company by 6-digit ticker or Chinese/English name fragment.

    Args:
        ticker_or_name: 6-digit ticker ("600519") or name fragment ("贵州茅台" / "MOUTAI").

    Returns: {stock_code, name, name_en, org_id, exchange, category} or {error}.
    """
    return T.get_company(ticker_or_name)


@app.tool
def list_filings(
    ticker_or_name: str,
    form: Optional[str] = None,
    category: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 20,
) -> dict:
    """List a CN-A-share company's CNINFO disclosures.

    Args:
        ticker_or_name: ticker or name (see get_company).
        form: optional Chinese form name (e.g. "年度报告", "半年度报告", "第一季度报告",
              "第三季度报告"). Free-text forms are filtered by title substring.
        category: optional CNINFO category — any catalog name (e.g. "招股说明书",
              "增发", "业绩预告") or raw `category_*` code. Use `list_report_types`
              to browse the catalog. Mutually exclusive with `form`; supplying both
              returns an error. Unknown categories return an error (no network call).
        year: optional fiscal-year filter (FY year, not publish year).
        limit: max rows to return (default 20).

    Each entry: {announcement_id, title, form, published, pdf_url, stock_code, company_name}.
    """
    result = T.list_filings(
        ticker_or_name, form=form, category=category, year=year, limit=limit
    )
    if isinstance(result, dict):  # error path
        return result
    return {"filings": result, "count": len(result)}


@app.tool
def get_filing(announcement_id: str, ticker_or_name: Optional[str] = None) -> dict:
    """Fetch one CNINFO announcement's metadata + PDF URL by id.

    Args:
        announcement_id: CNINFO announcementId.
        ticker_or_name: company hint to narrow the lookup (recommended).

    Returns: same shape as list_filings entries, or {error}.
    """
    return T.get_filing(announcement_id, ticker_or_name=ticker_or_name)


@app.tool
def get_financials(
    ticker_or_name: str,
    statement: Optional[str] = None,
    period: str = "annual",
) -> dict:
    """Return structured income/balance/cashflow statements for a CN-A-share company.

    Args:
        ticker_or_name: ticker or name (see get_company).
        statement: omit for all three; else one of
                   "income_statement" | "balance_sheet" | "cashflow".
        period: "annual" (default; keeps year-end rows) or "quarterly" (all periods).

    Each statement is serialized as {columns, data} (DataFrame.to_dict orient='split').
    """
    return T.get_financials(ticker_or_name, statement=statement, period=period)


@app.tool
def get_section(
    ticker_or_name: str,
    year: int,
    section: str,
    form: str = "年度报告",
) -> dict:
    """Resolve a company's filing PDF and extract one named section.

    Convenience wrapper: (ticker, year, section, form) → CNINFO lookup
    → PDF URL → existing outline-extraction pipeline.

    Args:
        ticker_or_name: ticker or name.
        year: fiscal year.
        section: exact title, regex, or 1-based ordinal — same selector
                 grammar as extract_section.
        form: form name; defaults to "年度报告".

    Returns: {stock_code, company_name, year, form, section, pdf_url,
              outline_entry, text, char_count} or {error}.
    """
    return T.get_section(ticker_or_name, year=year, section=section, form=form)


# ── report-type catalog + special-report tools ─────────────────


@app.tool
def list_report_types(group: Optional[str] = None) -> dict:
    """Browse the CNINFO disclosure category catalog.

    Args:
        group: optional group name to filter by (e.g. "定期报告", "融资", "业绩",
               "股权变动", "公司治理", "风险与特别处理"). Omit to list every group.

    Returns: each category as `{name, code, description}` plus a `count`.
    Useful before calling `list_filings(category=…)` or `get_special_report(…)`.
    """
    return T.list_report_types(group=group)


@app.tool
def get_special_report(
    ticker_or_name: str,
    category: str,
    year: Optional[int] = None,
    section: Optional[str] = None,
    limit: int = 5,
) -> dict:
    """Retrieve a special-type report for a CN-A-share company by CNINFO category.

    Args:
        ticker_or_name: ticker or name (see get_company).
        category: CNINFO category — a catalog name (e.g. "招股说明书", "收购报告书",
                  "业绩预告") or raw `category_*` code. Use `list_report_types` to browse.
        year: optional publish-year window (FY year for periodic reports).
        section: optional section selector (exact title, regex, or 1-based ordinal —
                 same grammar as `extract_section`). When omitted, the PDF is NOT
                 downloaded; only filing metadata + pdf_url are returned.
        limit: max filings to consider (default 5); the top (most recent) is used.

    Returns: filing metadata + pdf_url, plus section text/outline_entry/char_count
             when `section` is given; or an error field on unknown category / company / filing.
    """
    return T.get_special_report(
        ticker_or_name, category=category, year=year, section=section, limit=limit
    )


if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
