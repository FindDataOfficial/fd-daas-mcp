"""Unit tests for cnreport-mcp pure logic. No live ES/LLM/scrapling calls."""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp()
os.environ.setdefault("DAAS_DATABASE_URL", f"sqlite:///{_TMP}/test_cnreport.db")
# Keep the report cache off the repo during tests.
os.environ.setdefault("CNREPORT_CACHE_DIR", os.path.join(_TMP, "report_cache"))
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)

sys.path.insert(0, str(Path(__file__).resolve().parent))
_MODELS = Path(__file__).resolve().parent.parent / "models"
if str(_MODELS) not in sys.path:
    sys.path.insert(0, str(_MODELS))

import cnreport_tools as T  # noqa: E402

_FIXTURES = Path(__file__).resolve().parent / "test_fixtures"


def test_parse_outline_and_selectors():
    text = (
        "第三节 管理层讨论与分析 ......... 12\n"
        "第四节 公司治理 ......... 30\n"
        "第三节 管理层讨论与分析\n营收增长。\n"
        "第四节 公司治理\n治理完善。\n"
    )
    outline = T.parse_outline(text)
    titles = [e["title"] for e in outline]
    assert "第三节 管理层讨论与分析" in titles
    assert "第四节 公司治理" in titles

    assert T.resolve_selector(outline, "第三节 管理层讨论与分析")["ordinal"] == 1
    assert T.resolve_selector(outline, "2")["title"].startswith("第四节")
    assert T.resolve_selector(outline, "治理")["title"].startswith("第四节")
    assert T.resolve_selector(outline, "nope") is None


def test_extract_section_slice_stops_at_next_entry():
    text = (
        "第三节 管理层讨论与分析\n营收增长。\n"
        "第四节 公司治理\n治理完善。\n"
    )
    outline = T.parse_outline(text)
    entry = T.resolve_selector(outline, "第三节 管理层讨论与分析")
    body = T.extract_section_text(text, outline, entry)
    assert "营收增长" in body
    assert "治理完善" not in body


def test_records_to_docs_id_format():
    docs = T.records_to_docs([{"a": 1}, {"a": 2}], "r1", "s1")
    assert [d["_id"] for d in docs] == ["r1:s1:0", "r1:s1:1"]
    assert docs[1]["fields"]["a"] == 2


def test_ai_extract_without_api_key_errors():
    # server.py loads the real .env at import (repaving the key we popped
    # above), so clear it again after import — ai_extract reads env at call time.
    from server import ai_extract

    os.environ.pop("LLM_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)
    result = ai_extract(text="营业收入100", schema={"type": "object"})
    assert "error" in result and "LLM_API_KEY" in result["error"]


def test_delete_index_requires_confirm():
    from server import delete_index

    # confirm=False short-circuits before touching ES (no ES_URL set either)
    result = delete_index(year=2023, confirm=False)
    assert "error" in result and "confirm" in result["error"]


# ── company-API tests (CNINFO + akshare mocked at module boundary) ──


def _load_fixture(name: str):
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _patch_cninfo(monkeypatch, *, topsearch=None, hisann=None):
    """Patch the two `_post_json` calls cninfo_client makes."""
    import cninfo_client

    def fake_post(path, data):
        if "topSearch" in path:
            return topsearch if topsearch is not None else _load_fixture("cninfo_topsearch.json")
        if "hisAnnouncement" in path:
            return hisann if hisann is not None else _load_fixture("cninfo_hisannouncement.json")
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(cninfo_client, "_post_json", fake_post)


def test_get_company_by_ticker(monkeypatch):
    _patch_cninfo(monkeypatch)
    from server import get_company

    result = get_company("600519")
    assert result["stock_code"] == "600519"
    assert "茅台" in result["name"]
    assert result["exchange"] == "sse"
    assert result["org_id"] == "gssh0600519"


def test_get_company_by_name(monkeypatch):
    _patch_cninfo(monkeypatch)
    from server import get_company

    result = get_company("贵州茅台")
    assert result["stock_code"] == "600519"


def test_get_company_unknown_returns_error(monkeypatch):
    _patch_cninfo(monkeypatch, topsearch=[])
    from server import get_company

    result = get_company("ZZZZZZ")
    assert "error" in result


def test_list_filings_basic(monkeypatch):
    _patch_cninfo(monkeypatch)
    from server import list_filings

    result = list_filings("600519", limit=5)
    assert "filings" in result
    assert result["count"] >= 1
    f0 = result["filings"][0]
    assert f0["pdf_url"].startswith("http://static.cninfo.com.cn/")
    assert f0["stock_code"] == "600519"


def test_list_filings_filter_form(monkeypatch):
    _patch_cninfo(monkeypatch)
    from server import list_filings

    result = list_filings("600519", form="年度报告", limit=5)
    assert "filings" in result
    for row in result["filings"]:
        assert row["form"] == "年度报告" or "年度报告" in row["title"]


def test_list_filings_filter_year(monkeypatch):
    _patch_cninfo(monkeypatch)
    from server import list_filings

    result = list_filings("600519", form="年度报告", year=2023, limit=5)
    assert "filings" in result
    for row in result["filings"]:
        # FY 2023 reports publish in 2024 or have "2023" in the title
        assert "2023" in row["title"] or row["published"].startswith("2024-")


def test_get_filing_by_id(monkeypatch):
    _patch_cninfo(monkeypatch)
    from server import get_filing

    result = get_filing("1219730876", ticker_or_name="600519")
    assert result["announcement_id"] == "1219730876"
    assert result["pdf_url"].endswith(".PDF")


def test_get_filing_invalid_returns_error(monkeypatch):
    _patch_cninfo(monkeypatch)
    from server import get_filing

    result = get_filing("nonexistent", ticker_or_name="600519")
    assert "error" in result


def test_get_financials_all(monkeypatch):
    _patch_cninfo(monkeypatch)
    import financials_client

    def fake_get_statements(stock_code, *, period="annual", exchange=""):
        return {
            "income_statement": {"columns": ["报告日", "营业收入"], "data": [["2023-12-31", 100]]},
            "balance_sheet": {"columns": ["报告日", "总资产"], "data": [["2023-12-31", 500]]},
            "cashflow": {"columns": ["报告日", "经营现金流"], "data": [["2023-12-31", 80]]},
        }

    monkeypatch.setattr(financials_client, "get_statements", fake_get_statements)
    from server import get_financials

    result = get_financials("600519")
    assert "error" not in result
    assert result["stock_code"] == "600519"
    assert "income_statement" in result
    assert "balance_sheet" in result
    assert "cashflow" in result


def test_get_financials_single_statement(monkeypatch):
    _patch_cninfo(monkeypatch)
    import financials_client

    monkeypatch.setattr(
        financials_client,
        "get_statements",
        lambda stock_code, **_: {
            "income_statement": {"columns": ["x"], "data": [[1]]},
            "balance_sheet": {"columns": ["y"], "data": [[2]]},
            "cashflow": {"columns": ["z"], "data": [[3]]},
        },
    )
    from server import get_financials

    result = get_financials("600519", statement="balance_sheet")
    assert "balance_sheet" in result
    assert "income_statement" not in result
    assert result["statement"] == "balance_sheet"


def test_get_financials_missing_akshare_returns_error(monkeypatch):
    _patch_cninfo(monkeypatch)
    import financials_client

    def boom(*a, **kw):
        raise financials_client.MissingDependencyError("akshare not installed. test")

    monkeypatch.setattr(financials_client, "get_statements", boom)
    from server import get_financials

    result = get_financials("600519")
    assert "error" in result
    assert "akshare" in result["error"]


def test_get_financials_unknown_statement_returns_error(monkeypatch):
    _patch_cninfo(monkeypatch)
    import financials_client

    monkeypatch.setattr(
        financials_client,
        "get_statements",
        lambda stock_code, **_: {
            "income_statement": {"columns": [], "data": []},
            "balance_sheet": {"columns": [], "data": []},
            "cashflow": {"columns": [], "data": []},
        },
    )
    from server import get_financials

    result = get_financials("600519", statement="ebitda")
    assert "error" in result


def test_get_section_happy_path(monkeypatch):
    _patch_cninfo(monkeypatch)
    # Stub fetch_source to return canned annual-report text instead of
    # hitting the real PDF URL.
    fake_text = (
        "第三节 管理层讨论与分析\n经营情况良好。营业收入增长。\n"
        "第四节 公司治理\n治理结构完善。\n"
    )
    monkeypatch.setattr(T, "fetch_source_with_bytes", lambda *_a, **_kw: (fake_text, b"%PDF fake"))

    from server import get_section

    result = get_section("600519", year=2023, section="管理层讨论与分析")
    assert "error" not in result, result
    assert "经营情况良好" in result["text"]
    assert result["stock_code"] == "600519"
    assert result["pdf_url"].endswith(".PDF")


def test_get_section_unknown_section_returns_error(monkeypatch):
    _patch_cninfo(monkeypatch)
    monkeypatch.setattr(
        T, "fetch_source_with_bytes",
        lambda *_a, **_kw: ("第三节 管理层讨论与分析\n营收增长。\n", b"%PDF fake"),
    )

    from server import get_section

    result = get_section("600519", year=2023, section="No Such Section")
    assert "error" in result
    assert "available" in result


def test_get_section_no_filing_returns_error(monkeypatch):
    _patch_cninfo(monkeypatch, hisann={"announcements": []})
    from server import get_section

    result = get_section("600519", year=1900, section="管理层讨论与分析")
    assert "error" in result
    assert "no filing" in result["error"].lower()


def test_pdf_url_helper():
    import cninfo_client

    assert cninfo_client.pdf_url("finalpage/2024-04-02/abc.PDF") == (
        "http://static.cninfo.com.cn/finalpage/2024-04-02/abc.PDF"
    )
    # Already-absolute URLs pass through.
    assert cninfo_client.pdf_url("http://example.com/x.pdf") == "http://example.com/x.pdf"
    assert cninfo_client.pdf_url("") == ""


# ── report-type catalog + category tests ──────────────────────────


def test_load_categories_covers_four_forms():
    import cninfo_client

    cats = cninfo_client.load_categories()
    periodic = next(g for g in cats["groups"] if g["name"] == "定期报告")
    names = {c["name"] for c in periodic["categories"]}
    assert {"年度报告", "半年度报告", "第一季度报告", "第三季度报告"} <= names
    # the derived _FORM_CATEGORIES resolves to identical codes
    assert cninfo_client._FORM_CATEGORIES["年度报告"] == "category_ndbg_szsh"


def test_resolve_category_name_code_unknown_none():
    import cninfo_client

    assert cninfo_client.resolve_category("年度报告") == "category_ndbg_szsh"
    assert cninfo_client.resolve_category("首发") == "category_sf_szsh"
    # raw code passes through unchanged
    assert cninfo_client.resolve_category("category_ndbg_szsh") == "category_ndbg_szsh"
    # unknown / empty
    assert cninfo_client.resolve_category("不存在的类型") is None
    assert cninfo_client.resolve_category(None) is None
    assert cninfo_client.resolve_category("") is None


def test_load_categories_missing_file_raises(monkeypatch):
    import cninfo_client

    monkeypatch.setattr(cninfo_client, "_CATEGORIES_CACHE", None)
    monkeypatch.setattr(cninfo_client, "_REGISTRY_PATH", Path("/nonexistent/xyz.json"))
    with pytest.raises(FileNotFoundError):
        cninfo_client.load_categories()


def test_list_report_types_all_groups():
    from server import list_report_types

    r = list_report_types()
    assert "groups" in r
    assert r["count"] >= 26
    assert any(g["name"] == "定期报告" for g in r["groups"])
    # each category carries name + code
    g0 = r["groups"][0]
    assert all("name" in c and "code" in c for c in g0["categories"])


def test_list_report_types_filter_by_group():
    from server import list_report_types

    r = list_report_types(group="定期报告")
    names = [c["name"] for c in r["categories"]]
    assert names == ["年度报告", "半年度报告", "第一季度报告", "第三季度报告"]
    assert r["count"] == 4
    assert r["group"] == "定期报告"


def test_list_report_types_unknown_group_error():
    from server import list_report_types

    r = list_report_types(group="不存在的组")
    assert "error" in r
    assert "available" in r  # lists valid group names


def test_list_filings_category_name_sends_code(monkeypatch):
    """Filtering by a Chinese category name resolves and sends the code to CNINFO."""
    import cninfo_client

    captured = {}
    special = _load_fixture("cninfo_hisannouncement_special.json")

    def fake_post(path, data):
        if "topSearch" in path:
            return _load_fixture("cninfo_topsearch.json")
        if "hisAnnouncement" in path:
            captured["data"] = data
            return special
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(cninfo_client, "_post_json", fake_post)
    from server import list_filings

    result = list_filings("600519", category="首发", limit=5)
    assert "filings" in result
    assert captured["data"]["category"] == "category_sf_szsh"


def test_list_filings_category_raw_code_matches_name(monkeypatch):
    """A raw category_* code path produces the same CNINFO request as the name."""
    import cninfo_client

    captured = {}
    special = _load_fixture("cninfo_hisannouncement_special.json")

    def fake_post(path, data):
        if "topSearch" in path:
            return _load_fixture("cninfo_topsearch.json")
        if "hisAnnouncement" in path:
            captured["code"] = data["category"]
            return special
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(cninfo_client, "_post_json", fake_post)
    from server import list_filings

    list_filings("600519", category="category_sf_szsh", limit=3)
    assert captured["code"] == "category_sf_szsh"


def test_list_filings_unknown_category_no_network(monkeypatch):
    """An unknown category returns an error without hitting CNINFO."""
    import cninfo_client

    calls = {"n": 0}

    def fake_post(path, data):
        calls["n"] += 1
        return {}

    monkeypatch.setattr(cninfo_client, "_post_json", fake_post)
    from server import list_filings

    result = list_filings("600519", category="不存在的类型")
    assert "error" in result
    assert calls["n"] == 0  # no network call


def test_list_filings_form_and_category_mutually_exclusive(monkeypatch):
    _patch_cninfo(monkeypatch)
    from server import list_filings

    result = list_filings("600519", form="年度报告", category="首发")
    assert "error" in result
    assert "either" in result["error"]


def test_get_special_report_no_section_no_pdf_download(monkeypatch):
    _patch_cninfo(monkeypatch, hisann=_load_fixture("cninfo_hisannouncement_special.json"))
    fetch_calls = {"n": 0}

    def fake_fetch(*a, **k):
        fetch_calls["n"] += 1
        return "", b""

    monkeypatch.setattr(T, "fetch_source_with_bytes", fake_fetch)
    from server import get_special_report

    result = get_special_report("600519", category="首发")
    assert "error" not in result, result
    assert result["pdf_url"].endswith(".PDF")
    assert result["category"] == "首发"
    assert "text" not in result  # section omitted → no body
    assert fetch_calls["n"] == 0  # PDF NOT downloaded


def test_get_special_report_with_section(monkeypatch):
    _patch_cninfo(monkeypatch, hisann=_load_fixture("cninfo_hisannouncement_special.json"))
    monkeypatch.setattr(
        T,
        "fetch_source_with_bytes",
        lambda *_a, **_kw: (
            "第一节 募集资金运用\n募资10亿元用于扩产。\n"
            "第二节 风险因素\n市场风险。\n",
            b"%PDF fake",
        ),
    )
    from server import get_special_report

    result = get_special_report("600519", category="首发", section="募集资金运用")
    assert "error" not in result, result
    assert "募资10亿" in result["text"]
    assert result["char_count"] > 0
    assert result["pdf_url"].endswith(".PDF")


def test_get_special_report_by_raw_code(monkeypatch):
    _patch_cninfo(monkeypatch, hisann=_load_fixture("cninfo_hisannouncement_special.json"))
    monkeypatch.setattr(T, "fetch_source_with_bytes", lambda *_a, **_kw: ("第一节 募集资金运用\n内容。\n", b"%PDF fake"))
    from server import get_special_report

    result = get_special_report("600519", category="category_sf_szsh", section="募集资金运用")
    assert "error" not in result, result


def test_get_special_report_unknown_category_error(monkeypatch):
    _patch_cninfo(monkeypatch)
    from server import get_special_report

    result = get_special_report("600519", category="不存在的")
    assert "error" in result and "category" in result["error"].lower()


def test_get_special_report_no_filing_error(monkeypatch):
    _patch_cninfo(monkeypatch, hisann={"announcements": []})
    from server import get_special_report

    result = get_special_report("600519", category="首发")
    assert "error" in result
    assert "no filing" in result["error"].lower()


def test_get_special_report_unknown_company_error(monkeypatch):
    _patch_cninfo(monkeypatch, topsearch=[])
    from server import get_special_report

    result = get_special_report("ZZZZZZ", category="首发")
    assert "error" in result


def test_get_special_report_section_not_found(monkeypatch):
    _patch_cninfo(monkeypatch, hisann=_load_fixture("cninfo_hisannouncement_special.json"))
    monkeypatch.setattr(T, "fetch_source_with_bytes", lambda *_a, **_kw: ("第一节 募集资金运用\n内容。\n", b"%PDF fake"))
    from server import get_special_report

    result = get_special_report("600519", category="首发", section="No Such Section")
    assert "error" in result
    assert "available" in result
    assert "pdf_url" in result
