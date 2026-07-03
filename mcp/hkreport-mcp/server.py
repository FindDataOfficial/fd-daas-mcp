"""MCP Server for HK reports — HKEXnews filings + akshare financials.

Five tools mirroring edgartools-mcp's surface, with `get_disclosure_calendar`
replacing `get_insider_trades` (HK has no Form-4 equivalent agents query).
Keyless — HKEXnews + akshare HK endpoints are public.

Tools:
  get_company                 — resolve a HK-listed company by code or name
  list_filings                — list HKEXnews disclosures, filtered + collapsed
  get_filing                  — fetch one disclosure (metadata + PDF text)
  get_financials              — income / balance / cashflow via akshare
  get_disclosure_calendar     — upcoming results-announcement / AGM dates
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Callable, Optional

# Unified env: root .env first, then per-MCP .env with override=True
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

import httpx
from fastmcp import FastMCP

import hkex_client
import financials_client

app = FastMCP(name="hkreport-mcp")


# ── Error envelope ────────────────────────────────────────────────────


def _safe_tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Catch typed errors and return structured {error, hint} dicts."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except LookupError as e:
            return {"error": str(e), "hint": "Verify the ticker, doc_id, or query."}
        except ImportError as e:
            dep = str(e).split()[0] if str(e) else "dependency"
            return {"error": str(e) or f"{dep} import failed",
                    "hint": f"pip install {dep}"}
        except ValueError as e:
            return {"error": str(e), "hint": "Check the argument values."}
        except httpx.HTTPError as e:
            return {"error": f"HTTP error: {type(e).__name__}: {e}",
                    "hint": "Network or HKEXnews issue — retry, or set HTTPS_PROXY."}
        except Exception as e:  # last-ditch — never raise to the MCP client
            return {"error": f"{type(e).__name__}: {e}",
                    "hint": "Unexpected failure; check server logs."}

    return wrapper


# ── Helpers ───────────────────────────────────────────────────────────


def _resolve_code(ticker_or_name: str) -> str:
    """Resolve a ticker_or_name to a 5-digit HK stock code, or raise LookupError."""
    direct = hkex_client._normalize_ticker(ticker_or_name)
    if direct:
        return direct
    company = hkex_client.lookup_company(ticker_or_name)
    return company["stock_code"]


# ── Tools ─────────────────────────────────────────────────────────────


@app.tool
@_safe_tool
def get_company(ticker_or_name: str) -> dict:
    """Resolve a HK-listed company by code (`00700` / `0700.HK`) or name fragment.

    Args:
        ticker_or_name: 5-digit HK stock code, `.HK`-suffixed form, or name fragment.
    """
    return hkex_client.lookup_company(ticker_or_name)


@app.tool
@_safe_tool
def list_filings(
    ticker_or_name: str,
    form: Optional[str] = None,
    year: Optional[int] = None,
    language: Optional[str] = None,
    limit: int = 20,
) -> list[dict] | dict:
    """List HKEXnews disclosures for a HK company.

    Args:
        ticker_or_name: ticker or name.
        form: optional doc-type filter (`Annual Report`, `Interim Report`, ...).
        year: optional 4-digit calendar year filter.
        language: optional `en`/`zh`/`both` filter.
        limit: max disclosures returned (default 20).
    """
    code = _resolve_code(ticker_or_name)
    return hkex_client.list_announcements(
        code, doc_type=form, year=year, language=language, limit=max(1, min(limit, 200))
    )


@app.tool
@_safe_tool
def get_filing(doc_id_or_url: str, detail: str = "standard") -> dict:
    """Fetch a single HKEXnews disclosure by doc_id or canonical URL.

    Args:
        doc_id_or_url: HKEXnews doc_id (e.g. `2024/0820/2024082000123`) or full PDF URL.
        detail: `minimal` (metadata only), `standard` (~50 KB text), `full` (~200 KB).
    """
    cap = {"minimal": 0, "standard": 50_000, "full": 200_000}.get(detail)
    if cap is None:
        return {"error": f"detail must be one of minimal/standard/full (got {detail!r})",
                "hint": "Use detail='standard'."}
    return hkex_client.fetch_announcement(
        doc_id_or_url, with_text=cap > 0, text_cap_bytes=cap
    )


@app.tool
@_safe_tool
def get_financials(
    ticker_or_name: str,
    statement: Optional[str] = None,
    period: str = "annual",
) -> dict:
    """Return HK financial statements via akshare.

    Args:
        ticker_or_name: ticker or name.
        statement: optional single statement (`income_statement` / `balance_sheet` / `cashflow`).
                   When omitted, all three are returned.
        period: `annual` (default) or `interim`. HK has no quarterly filings.
    """
    if period not in ("annual", "interim"):
        return {"error": f"period must be 'annual' or 'interim' (got {period!r})",
                "hint": "Use period='annual'."}
    code = _resolve_code(ticker_or_name)
    if statement is None:
        return financials_client.fetch_all(code, period=period)
    if statement not in financials_client._INDICATORS:
        valid = "/".join(financials_client._INDICATORS)
        return {"error": f"statement must be one of {valid} (got {statement!r})",
                "hint": f"Use statement in [{valid}]."}
    return {statement: financials_client.fetch_one(code, statement, period=period)}


@app.tool
@_safe_tool
def get_disclosure_calendar(
    ticker_or_name: str,
    kind: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """List upcoming results-announcement and AGM dates for a HK company.

    Args:
        ticker_or_name: ticker or name.
        kind: optional `results` or `agm` filter (default both).
        limit: max entries (default 10).
    """
    code = _resolve_code(ticker_or_name)
    entries = hkex_client.list_calendar(code, kind=kind)
    return entries[: max(1, min(limit, 200))]


# ── Entrypoint ────────────────────────────────────────────────────────


if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
