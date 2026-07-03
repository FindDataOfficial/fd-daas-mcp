"""
MCP Server for edinet-tools — Japan EDINET disclosures.

Purpose-built (not a registry/harness) because `edinet_tools` exposes a small
object/functional model (Entity / Document / ParsedReport), not a flat function
catalog.

Tools:
  search_entities     — name search (ticker/E-code/name), keyless
  get_entity          — entity facts by ticker / EDINET code / corporate number, keyless
  list_documents      — filings filed on a date, optionally filtered by doc-type code
  get_document        — fetch + parse a single document by doc ID
  supported_doc_types — all 42 EDINET doc-type codes with names/descriptions, keyless

API key: EDINET requires EDINET_API_KEY only for document *fetching*
(documents() / parse()). Entity lookup and doc-type metadata work without a
key. Set EDINET_API_KEY in root .env (preferred) or this dir's .env.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# Unified env: root .env first, then per-MCP .env with override=True
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

from fastmcp import FastMCP

app = FastMCP(name="edinet-mcp")

# The library reads EDINET_API_KEY from env lazily inside _get_client(); we just
# track whether it is configured so the document tools can fail fast with a
# clear message instead of an opaque API error.
_API_KEY_OK: bool = bool(os.environ.get("EDINET_API_KEY", "").strip())


# ── Guards & serialization ────────────────────────────────────────────


def _require_api_key() -> Optional[dict]:
    """Return an error dict if EDINET_API_KEY is not set, else None."""
    if not _API_KEY_OK:
        return {
            "error": "EDINET_API_KEY is not set",
            "hint": "Set EDINET_API_KEY in root .env — required only for "
            "list_documents / get_document. Entity and doc-type tools work without it.",
        }
    return None


def _import_edinet():
    """Lazy-import edinet_tools, returning (module, error_dict)."""
    try:
        import edinet_tools

        return edinet_tools, None
    except ImportError:
        return None, {
            "error": "edinet-tools is not installed",
            "hint": "Install with: pip install edinet-tools",
        }


def _serialize(result: Any, depth: int = 0, max_depth: int = 4) -> Any:
    """Convert an edinet_tools result to a JSON-serializable value."""
    if depth > max_depth:
        return str(result)

    # Lazy pandas import
    try:
        import pandas as pd
    except ImportError:
        pd = None  # type: ignore

    if pd is not None and isinstance(result, pd.DataFrame):
        clean = result.where(result.notna(), None)
        return {
            "type": "dataframe",
            "shape": list(result.shape),
            "columns": [str(c) for c in result.columns],
            "data": clean.to_dict(orient="records"),
        }
    if pd is not None and isinstance(result, pd.Series):
        clean = result.where(result.notna(), None)
        return {
            "type": "series",
            "length": len(result),
            "name": str(result.name) if result.name is not None else None,
            "data": clean.to_dict(),
        }
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    if isinstance(result, dict):
        return {str(k): _serialize(v, depth + 1, max_depth) for k, v in result.items()}
    if isinstance(result, (list, tuple, set)):
        return [_serialize(v, depth + 1, max_depth) for v in result]

    # Objects exposing to_dict() (ParsedReport, ...): prefer it.
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        try:
            return _serialize(to_dict(), depth + 1, max_depth)
        except Exception:
            pass

    # Dataclasses / __dict__-bearing objects: flatten public, non-callable attrs.
    if hasattr(result, "__dict__"):
        d = {}
        for k, v in vars(result).items():
            if k.startswith("_") or callable(v):
                continue
            d[k] = _serialize(v, depth + 1, max_depth)
        if d:
            return d

    # Fallback: enumerate public non-callable attributes; else stringify.
    out: dict[str, Any] = {}
    for a in dir(result):
        if a.startswith("_"):
            continue
        try:
            v = getattr(result, a)
        except Exception:
            continue
        if callable(v):
            continue
        out[a] = _serialize(v, depth + 1, max_depth)
    if out:
        return out
    return {"type": "scalar", "data": str(result)}


# ── Entity serialization ──────────────────────────────────────────────


# Entity exposes its data via properties (the only __dict__ attr is _data), so
# pull a curated set explicitly. Avoid the deprecated is_listed / is_fund_issuer.
_ENTITY_FIELDS = [
    "edinet_code", "name", "name_jp", "name_en", "name_phonetic",
    "ticker", "entity_type", "submitter_type", "industry", "province",
    "capital", "accounting_period_end", "corporate_number",
]


def _entity_summary(entity) -> dict:
    out: dict[str, Any] = {}
    for f in _ENTITY_FIELDS:
        try:
            v = getattr(entity, f)
        except Exception:
            continue
        # entity_type is an EntityType enum; stringify for JSON.
        if hasattr(v, "name") and not isinstance(v, (str, int, float, bool)):
            v = getattr(v, "name", str(v))
        out[f] = _serialize(v, max_depth=2)
    return out


# ── Document serialization ────────────────────────────────────────────


def _document_summary(doc) -> dict:
    """Extract a flat summary dict from a Document object."""
    filed = getattr(doc, "filing_datetime", None)
    return {
        "doc_id": getattr(doc, "doc_id", None),
        "doc_type_code": getattr(doc, "doc_type_code", None),
        "doc_type_name": getattr(doc, "doc_type_name", None),
        "filer_edinet_code": getattr(doc, "filer_edinet_code", None),
        "filer_name": getattr(doc, "filer_name", None),
        "securities_code": getattr(doc, "securities_code", None),
        "filed": filed.isoformat() if filed is not None else None,
        "period_start": getattr(doc, "period_start", None),
        "period_end": getattr(doc, "period_end", None),
        "doc_description": getattr(doc, "doc_description", None),
    }


# ── Tools ─────────────────────────────────────────────────────────────


@app.tool
def search_entities(query: str, limit: int = 10) -> dict:
    """Search EDINET entities by name (Japanese or English).

    Handles full-width/half-width and gaiji normalization via the library.

    Args:
        query: Search string — matches Japanese or English names.
        limit: Max results to return (default 10, max 100).
    """
    edinet, err = _import_edinet()
    if err:
        return err

    limit = max(1, min(int(limit), 100))
    try:
        results = edinet.search_entities(query, limit=limit)
    except Exception as e:
        return {"error": f"search_entities failed: {type(e).__name__}: {e}"}

    rows = [_entity_summary(e) for e in results]
    return {"count": len(rows), "query": query, "entities": rows}


@app.tool
def get_entity(ticker_or_code: str) -> dict:
    """Look up an EDINET entity by ticker, EDINET code, name, or corporate number.

    Args:
        ticker_or_code: Ticker (e.g. "7203"), EDINET code (e.g. "E02144"),
            company name, or 13-digit corporate number (法人番号).
    """
    edinet, err = _import_edinet()
    if err:
        return err

    ident = (ticker_or_code or "").strip()
    if not ident:
        return {"error": "ticker_or_code is required"}

    try:
        # 13-digit all-digits → corporate number path; else smart entity().
        if ident.isdigit() and len(ident) == 13:
            entity = edinet.entity_by_corporate_number(ident)
        else:
            entity = edinet.entity(ident)
    except Exception as e:
        return {"error": f"entity lookup failed: {type(e).__name__}: {e}"}

    if entity is None:
        return {"error": f"No entity found for '{ticker_or_code}'"}
    return _entity_summary(entity)


@app.tool
def list_documents(
    date: str,
    doc_type: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """List EDINET documents filed on a given date.

    Args:
        date: Filing date as YYYY-MM-DD (JST).
        doc_type: Optional doc-type code filter (e.g. "120", "350").
        limit: Max documents to return (default 50, max 500).
    """
    if err := _require_api_key():
        return err
    edinet, err = _import_edinet()
    if err:
        return err

    limit = max(1, min(int(limit), 500))
    try:
        docs = edinet.documents(date, doc_type=doc_type)
    except Exception as e:
        return {"error": f"list_documents failed: {type(e).__name__}: {e}"}

    rows = [_document_summary(d) for d in docs[:limit]]
    return {"count": len(rows), "date": date, "doc_type": doc_type, "documents": rows}


@app.tool
def get_document(
    doc_id: str,
    doc_type_code: Optional[str] = None,
    detail: str = "standard",
) -> dict:
    """Fetch and parse a single EDINET document by document ID.

    Args:
        doc_id: EDINET document ID (e.g. "S100ABC").
        doc_type_code: Doc-type code (e.g. "120", "350"). Recommended — routes to
            the typed parser. If omitted, a generic raw parse is used.
        detail: Payload size — "minimal" (mapped fields only), "standard"
            (default, adds raw_fields + text_blocks), or "full" (deep serialize).
    """
    if err := _require_api_key():
        return err
    edinet, err = _import_edinet()
    if err:
        return err

    try:
        report = edinet.fetch_and_parse(doc_id, doc_type_code or "")
    except Exception as e:
        return {"error": f"get_document failed: {type(e).__name__}: {e}"}

    if report is None:
        return {"error": f"Document '{doc_id}' could not be fetched or parsed"}

    out: dict[str, Any] = {
        "doc_id": getattr(report, "doc_id", doc_id),
        "doc_type_code": getattr(report, "doc_type_code", doc_type_code),
        "report_type": type(report).__name__,
        "fields": _serialize(report.to_dict(), max_depth=3),
    }

    if detail != "minimal":
        out["raw_fields"] = _serialize(getattr(report, "raw_fields", {}), max_depth=3)
        out["text_blocks"] = _serialize(getattr(report, "text_blocks", {}), max_depth=2)
        if detail == "full":
            out["unmapped_fields"] = _serialize(
                getattr(report, "unmapped_fields", {}), max_depth=3
            )
    return out


@app.tool
def supported_doc_types() -> dict:
    """Return all EDINET document-type codes with names/descriptions.

    Marks which codes have typed parsers (vs raw fallback). Keyless.
    """
    edinet, err = _import_edinet()
    if err:
        return err

    try:
        all_types = edinet.doc_types()  # list[DocType]
        typed = set(edinet.supported_doc_types())  # codes with typed parsers
    except Exception as e:
        return {"error": f"supported_doc_types failed: {type(e).__name__}: {e}"}

    rows = [
        {
            "code": dt.code,
            "name_en": dt.name_en,
            "name_jp": dt.name_jp,
            "description": dt.description,
            "has_typed_parser": dt.code in typed,
        }
        for dt in all_types
    ]
    return {"count": len(rows), "doc_types": rows}


# ── Self-check ────────────────────────────────────────────────────────


def _selfcheck() -> None:
    """Opt-in smoke check: doc-type metadata is keyless and stable."""
    edinet, err = _import_edinet()
    if err:
        print("SKIP:", err["error"])
        return
    types = edinet.doc_types()
    assert types, "expected at least one doc type"
    assert any(dt.code == "120" for dt in types), "expected securities-report code 120"
    print(f"OK: {len(types)} doc types; sample = {types[0].code} {types[0].name_en}")


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        app.run(transport="stdio", show_banner=False)
