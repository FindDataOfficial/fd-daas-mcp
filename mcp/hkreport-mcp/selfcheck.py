"""Offline selfcheck for hkreport-mcp.

Mocks HKEXnews HTTP endpoints with respx and patches akshare.
Run: uv run --directory mcp/hkreport-mcp python selfcheck.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import respx

import hkex_client
import financials_client


# ── Fixture responses ─────────────────────────────────────────────────

INSTRUMENT_JSON = [
    {"stockId": "00700", "name_en": "Tencent Holdings Ltd.", "name_zh": "騰訊控股",
     "board": "Main", "sector": "Technology", "industry": "Internet Software"},
]

TITLE_SEARCH_JSON = {
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

# minimal-but-valid PDF that pypdf accepts (1 page, no text)
_PDF_BYTES = (
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000015 00000 n \n"
    b"0000000060 00000 n \n0000000108 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF\n"
)

CALENDAR_HTML = """
<table><tr><td>2024-08-15</td><td>00700</td><td>Interim Results Announcement</td></tr>
<tr><td>2025-05-20</td><td>00700</td><td>Annual General Meeting</td></tr></table>
"""


def _build_mock() -> respx.MockRouter:
    router = respx.mock(assert_all_called=False)
    router.get(hkex_client._INSTRUMENT_SEARCH).respond(
        200, json=INSTRUMENT_JSON
    )
    router.get(hkex_client._TITLE_SEARCH).respond(
        200, content=json.dumps(TITLE_SEARCH_JSON), headers={"content-type": "application/json"}
    )
    router.get(hkex_client._CALENDAR).respond(200, text=CALENDAR_HTML)
    # PDF fetch — any path under hkexnews.hk/listedco/listconews/...
    router.get(url__regex=r".*listedco/listconews/.*\.pdf$").respond(
        200, content=_PDF_BYTES, headers={"content-type": "application/pdf"}
    )
    return router


def _fake_ak_report(stock: str, symbol: str, indicator: str):
    import pandas as pd
    return pd.DataFrame({
        "REPORT_DATE": ["2023-12-31", "2022-12-31"],
        "ITEM": [symbol, symbol],
        "VALUE": [100.0, float("nan")],
    })


def main() -> int:
    from server import (
        get_company,
        list_filings,
        get_filing,
        get_financials,
        get_disclosure_calendar,
    )

    with _build_mock(), patch.object(
        financials_client, "_import_akshare",
        return_value=type("ak", (), {"stock_financial_hk_report_em": staticmethod(_fake_ak_report)}),
    ):
        # 1. get_company
        r = get_company("00700")
        assert r.get("stock_code") == "00700", r
        assert "Tencent" in r.get("name", ""), r
        print(f"  ✓ get_company: {r['stock_code']} {r['name']}")

        # 2. list_filings — should collapse the en + zh duplicates into one entry
        r = list_filings("00700", limit=5)
        assert isinstance(r, list) and len(r) == 1, r
        assert len(r[0]["documents"]) == 2, r[0]
        assert r[0]["language"] == "both", r[0]
        print(f"  ✓ list_filings: {len(r)} entry, {len(r[0]['documents'])} languages")

        # 3. get_filing — minimal (no text)
        r = get_filing("https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0820/2024082000123.pdf",
                       detail="minimal")
        assert r.get("doc_id") == "2024082000123", r
        assert "text" not in r, r
        print(f"  ✓ get_filing (minimal): doc_id={r['doc_id']}")

        # 4. get_financials
        r = get_financials("00700", statement="income_statement", period="annual")
        assert "income_statement" in r, r
        assert r["income_statement"]["columns"] == ["REPORT_DATE", "ITEM", "VALUE"], r
        # NaN survived as None
        assert r["income_statement"]["data"][1]["VALUE"] is None, r
        print(f"  ✓ get_financials: {len(r['income_statement']['data'])} rows")

        # 5. get_disclosure_calendar
        r = get_disclosure_calendar("00700", limit=5)
        assert isinstance(r, list) and len(r) == 2, r
        assert {e["kind"] for e in r} == {"results", "agm"}, r
        print(f"  ✓ get_disclosure_calendar: {len(r)} entries")

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
