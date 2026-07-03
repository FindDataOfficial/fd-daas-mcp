"""Offline unit tests for hkreport-mcp.

Network is mocked via respx; akshare is monkeypatched. Live-network tests
gated behind HKREPORT_LIVE=1.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pytest
import respx

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hkex_client
import financials_client


# ── _normalize_ticker ─────────────────────────────────────────────────


@pytest.mark.parametrize("value,expected", [
    ("00700", "00700"),
    ("700", "00700"),
    ("0700.HK", "00700"),
    ("700.HK", "00700"),
    ("9988", "09988"),
    ("09988.HK", "09988"),
    (" 00001 ", "00001"),
    ("", None),
    ("abc", None),
    ("Tencent", None),
    ("123456", None),  # too many digits
])
def test_normalize_ticker(value, expected):
    assert hkex_client._normalize_ticker(value) == expected


# ── duplicate collapsing ──────────────────────────────────────────────


def test_collapse_duplicates_merges_languages():
    raw = [
        {"doc_id": "a", "title": "Annual Report 2023", "form": "Annual Report",
         "published": "2024-04-01", "language": "en", "stock_code": "00700",
         "url": "https://x/en.pdf"},
        {"doc_id": "b", "title": "年報 2023", "form": "Annual Report",
         "published": "2024-04-01", "language": "zh", "stock_code": "00700",
         "url": "https://x/zh.pdf"},
    ]
    out = hkex_client._collapse_duplicates(raw, limit=10)
    assert len(out) == 1
    assert {d["lang"] for d in out[0]["documents"]} == {"en", "zh"}
    assert out[0]["language"] == "both"


def test_collapse_duplicates_keeps_distinct_dates():
    raw = [
        {"doc_id": "a", "title": "Annual Report", "form": "Annual Report",
         "published": "2024-04-01", "language": "en", "stock_code": "00700",
         "url": "https://x/a.pdf"},
        {"doc_id": "b", "title": "Annual Report", "form": "Annual Report",
         "published": "2023-04-01", "language": "en", "stock_code": "00700",
         "url": "https://x/b.pdf"},
    ]
    out = hkex_client._collapse_duplicates(raw, limit=10)
    assert len(out) == 2


# ── lookup_company (HTTP mocked) ──────────────────────────────────────


_INSTRUMENT_JSON = [
    {"stockId": "00700", "name_en": "Tencent Holdings Ltd.", "name_zh": "騰訊控股",
     "board": "Main", "sector": "Technology", "industry": "Internet Software"},
]


@respx.mock
def test_lookup_company_by_ticker():
    respx.get(hkex_client._INSTRUMENT_SEARCH).respond(200, json=_INSTRUMENT_JSON)
    r = hkex_client.lookup_company("00700")
    assert r["stock_code"] == "00700"
    assert r["name"].startswith("Tencent")
    assert r["name_zh"] == "騰訊控股"


@respx.mock
def test_lookup_company_empty_raises():
    respx.get(hkex_client._INSTRUMENT_SEARCH).respond(200, json=[])
    with pytest.raises(LookupError):
        hkex_client.lookup_company("ZZZZZZ")


@respx.mock
def test_lookup_company_network_error_propagates():
    respx.get(hkex_client._INSTRUMENT_SEARCH).mock(
        side_effect=httpx.ConnectError("boom")
    )
    with pytest.raises(httpx.HTTPError):
        hkex_client.lookup_company("00700")


# ── list_announcements ────────────────────────────────────────────────


_TITLE_SEARCH_JSON = {
    "data": [
        {"FILE_ID": "2024082000123", "DATE_TIME": "2024-08-20",
         "TITLE": "Interim Report 2024", "LONG_TEXT": "Interim Report",
         "STOCK_CODE": "00700",
         "FILE_LINK": "/listedco/listconews/sehk/2024/0820/2024082000123.pdf",
         "FILE_TYPE": "E"},
        {"FILE_ID": "2024082000124", "DATE_TIME": "2024-08-20",
         "TITLE": "中期報告 2024", "LONG_TEXT": "中期報告",
         "STOCK_CODE": "00700",
         "FILE_LINK": "/listedco/listconews/sehk/2024/0820/2024082000124.pdf",
         "FILE_TYPE": "C"},
    ]
}


@respx.mock
def test_list_announcements_collapses_languages():
    respx.get(hkex_client._TITLE_SEARCH).respond(200, json=_TITLE_SEARCH_JSON)
    out = hkex_client.list_announcements("00700")
    assert len(out) == 1
    assert len(out[0]["documents"]) == 2
    assert out[0]["language"] == "both"


@respx.mock
def test_list_announcements_empty_returns_empty():
    respx.get(hkex_client._TITLE_SEARCH).respond(200, json={"data": []})
    assert hkex_client.list_announcements("00700") == []


# ── fetch_announcement ────────────────────────────────────────────────


_PDF_BYTES = (
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000015 00000 n \n"
    b"0000000060 00000 n \n0000000108 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF\n"
)


@respx.mock
def test_fetch_announcement_minimal():
    url = "https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0820/2024082000123.pdf"
    respx.get(url).respond(200, content=_PDF_BYTES)
    out = hkex_client.fetch_announcement(url, with_text=False)
    assert out["doc_id"] == "2024082000123"
    assert out["size_bytes"] > 0
    assert "text" not in out


@respx.mock
def test_fetch_announcement_404_raises():
    url = "https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0820/missing.pdf"
    respx.get(url).respond(404)
    with pytest.raises(LookupError):
        hkex_client.fetch_announcement(url, with_text=False)


# ── server tools — error envelope ─────────────────────────────────────


@respx.mock
def test_server_get_company_unknown_returns_error_dict():
    respx.get(hkex_client._INSTRUMENT_SEARCH).respond(200, json=[])
    from server import get_company
    r = get_company("ZZZZZZ")
    assert "error" in r and "hint" in r


@respx.mock
def test_server_get_filing_network_error_returns_dict():
    url = "https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0820/x.pdf"
    respx.get(url).mock(side_effect=httpx.ConnectError("boom"))
    from server import get_filing
    r = get_filing(url, detail="minimal")
    assert "error" in r and "HTTP" in r["error"]


@respx.mock
def test_server_get_financials_missing_akshare_returns_error(monkeypatch):
    # Build a normalize-ticker shortcut that doesn't touch HTTP.
    from server import get_financials

    def boom():
        raise ImportError("akshare is not installed")

    monkeypatch.setattr(financials_client, "_import_akshare", boom)
    r = get_financials("00700", statement="income_statement")
    assert "error" in r and "akshare" in r["error"]


def test_server_get_filing_bad_detail_returns_error():
    from server import get_filing
    r = get_filing("any", detail="bogus")
    assert "error" in r and "minimal/standard/full" in r["error"]


def test_server_get_financials_bad_period_returns_error():
    from server import get_financials
    r = get_financials("00700", period="quarterly")
    assert "error" in r and "period" in r["error"]


# ── get_disclosure_calendar ───────────────────────────────────────────


@respx.mock
def test_get_disclosure_calendar_parses_html():
    html = ("<table>"
            "<tr><td>2024-08-15</td><td>00700</td><td>Interim Results Announcement</td></tr>"
            "<tr><td>2025-05-20</td><td>00700</td><td>Annual General Meeting</td></tr>"
            "</table>")
    respx.get(hkex_client._CALENDAR).respond(200, text=html)
    out = hkex_client.list_calendar("00700")
    assert {e["kind"] for e in out} == {"results", "agm"}
    assert out[0]["date"] == "2024-08-15"


@respx.mock
def test_get_disclosure_calendar_no_entries_returns_empty():
    respx.get(hkex_client._CALENDAR).respond(200, text="<html>no rows</html>")
    assert hkex_client.list_calendar("00700") == []


# ── financials ────────────────────────────────────────────────────────


def test_serialize_df_nan_to_none():
    import pandas as pd
    df = pd.DataFrame({"a": [1, 2], "b": [3.0, float("nan")]})
    out = financials_client._serialize_df(df)
    assert out["columns"] == ["a", "b"]
    assert out["data"][1]["b"] is None


def test_fetch_one_bad_statement():
    with pytest.raises(ValueError):
        financials_client._fetch("00700", "bogus", "annual")


# ── live smoke (only when HKREPORT_LIVE=1) ────────────────────────────


@pytest.mark.skipif(not os.environ.get("HKREPORT_LIVE"), reason="live")
def test_live_list_filings_00700():
    from server import list_filings
    r = list_filings("00700", limit=3)
    assert isinstance(r, list) and r, r


@pytest.mark.skipif(not os.environ.get("HKREPORT_LIVE"), reason="live")
def test_live_get_financials_00700():
    from server import get_financials
    r = get_financials("00700", statement="income_statement")
    assert "income_statement" in r and r["income_statement"]["data"], r
