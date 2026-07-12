"""Self-check for daas-mcp management domain.

Exercises every spec scenario for datasource-management, category-tree,
forms-sections, collections, and multi-level search against a TEMP db
(does not touch daas.db). Run: uv run python selfcheck.py

ponytail: assert-based, no framework. Fails fast and loud if logic breaks.
"""
from __future__ import annotations

import os
import tempfile


def main() -> int:
    # Temp DB — never touches the real daas.db
    db_path = tempfile.mktemp(suffix=".db")
    os.environ["DAAS_DATABASE_URL"] = f"sqlite:///{db_path}"
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    from daas_database import Database
    from registry_service import RegistryService
    from models import (
        Category,
        DaasSource,
        DaasFunction,
        DaasFunctionColumn,
        Entity,
        EntityDatasourceLink,
    )

    db = Database.get_instance()
    s = RegistryService(db.get_session())

    # ---- Category tree ----
    finance = s.create_category("finance", "Finance")
    usd = s.create_category("us-disclosure", "US Disclosure", parent_id=finance["id"])
    edgar_cat = s.create_category("edgar", "EDGAR", parent_id=usd["id"])
    assert s.get_subtree_ids(finance["id"]) == [finance["id"], usd["id"], edgar_cat["id"]], "subtree ids"

    # Cycle / self-parent rejection
    try:
        s.move_category(finance["id"], edgar_cat["id"])
        assert False, "cycle move should reject"
    except ValueError:
        pass
    try:
        s.move_category(finance["id"], finance["id"])
        assert False, "self-parent should reject"
    except ValueError:
        pass

    # Delete category with children rejected
    try:
        s.delete_category(finance["id"])
        assert False, "delete-with-children should reject"
    except ValueError:
        pass

    # ---- Datasource CRUD ----
    edgar = s.create_datasource("edgar", "SEC EDGAR", category_id=edgar_cat["id"], description="SEC filings")
    assert edgar["category_path"] == ["finance", "us-disclosure", "edgar"], "category_path"

    # Dup name rejected
    try:
        s.create_datasource("edgar", "dup")
        assert False, "dup name should reject"
    except ValueError:
        pass
    # Nonexistent category rejected
    try:
        s.create_datasource("x", "x", category_id=999)
        assert False, "nonexistent category should reject"
    except ValueError:
        pass

    # Update + clear category
    s.update_datasource(name="edgar", label="SEC EDGAR Filings")
    s.update_datasource(name="edgar", clear_category=True)
    assert s._resolve_source("edgar", None).category_id is None, "clear category"
    s.update_datasource(name="edgar", category_id=edgar_cat["id"])

    # ---- Forms & sections ----
    f10k = s.add_form("edgar", "10-K", "Annual Report")
    s.add_section(f10k["id"], "Item 1 Business", "Extract company description.")
    sec7 = s.add_section(f10k["id"], "Item 7 MD&A", "Extract MD&A.")
    f8k = s.add_form("edgar", "8-K")
    forms = s.list_forms("edgar")
    assert {f["form_type"] for f in forms} == {"10-K", "8-K"}, "forms list"
    assert len(forms[0]["sections"]) == 2, "10-K has 2 sections"
    # Unknown source rejected
    try:
        s.add_form("nope", "10-K")
        assert False
    except ValueError:
        pass
    # Unknown form rejected
    try:
        s.add_section(999, "x")
        assert False
    except ValueError:
        pass

    # ---- Collections ----
    coll = s.create_collection("us-disc", "US disclosure collection")
    s.add_to_collection("us-disc", "edgar")  # whole datasource
    s.add_to_collection("us-disc", "edgar", section_name="Item 7 MD&A")  # specific section
    listed = s.list_collection("us-disc")
    assert len(listed["items"]) == 2, "collection has 2 items"
    whole = [i for i in listed["items"] if i["section_name"] is None]
    granular = [i for i in listed["items"] if i["section_name"] == "Item 7 MD&A"]
    assert len(whole) == 1 and len(granular) == 1, "collection item shapes"
    assert granular[0]["instruction"] == "Extract MD&A.", "instruction resolved"
    # Dup item rejected
    try:
        s.add_to_collection("us-disc", "edgar")
        assert False
    except ValueError:
        pass
    # Unknown section rejected
    try:
        s.add_to_collection("us-disc", "edgar", section_name="Nope")
        assert False
    except ValueError:
        pass
    # Remove item
    s.remove_from_collection("us-disc", "edgar")  # removes whole-datasource item
    assert len(s.list_collection("us-disc")["items"]) == 1, "remove item"

    # ---- Multi-level search ----
    # category subtree
    res = s.search_datasources(category_id=finance["id"])
    assert [r["name"] for r in res] == ["edgar"], "subtree search"
    # category no subtree
    res = s.search_datasources(category_id=finance["id"], include_subtree=False)
    assert res == [], "no-subtree search returns empty"
    # drill to section
    res = s.search_datasources(source_name="edgar", section="Item 7")
    assert len(res) == 1 and res[0]["forms"][0]["form_type"] == "10-K", "section drill"
    assert len(res[0]["forms"][0]["sections"]) == 1, "section drill returns 1 section"
    # free-text query via section name
    res = s.search_datasources(query="MD&A")
    assert [r["name"] for r in res] == ["edgar"], "query MD&A"
    # free-text query via instruction
    res = s.search_datasources(query="company")
    assert [r["name"] for r in res] == ["edgar"], "query via instruction"
    # free-text query via form label
    res = s.search_datasources(query="Annual")
    assert [r["name"] for r in res] == ["edgar"], "query via form label"
    # no filters returns all (compact)
    res = s.search_datasources()
    assert len(res) == 1 and "forms" not in res[0], "compact no-filter shape"

    # ---- Cascade delete ----
    s.delete_datasource("edgar")
    assert len(s.list_collection("us-disc")["items"]) == 0, "cascade: collection items removed"
    assert s.search_datasources(source_name="edgar") == [], "cascade: source gone"

    # ---- Leaf category delete nulls datasource category ----
    leaf = s.create_category("leaf", "Leaf")
    src2 = s.create_datasource("s2", "Source Two", category_id=leaf["id"])
    s.delete_category(leaf["id"])
    sess = db.get_session()
    assert sess.get(DaasSource, src2["id"]).category_id is None, "leaf delete nulls category_id"
    assert sess.get(Category, leaf["id"]) is None, "leaf category removed"

    # ---- Entity domain ----
    # Two sources: one daas-registered (columns resolved locally), one
    # external-MCP-style (no daas_functions → column_hint from instruction).
    yf = s.create_datasource("yfinance", "Yahoo Finance")
    fyf = s.add_form("yfinance", "default", "Yahoo Finance tool catalog")
    s.add_section(
        fyf["id"],
        "Price-History",
        "mcp=yfinance-mcp tool=call_yfinance_function param=name=ticker_history param=params_json=<ask-agent>",
    )
    cn = s.create_datasource("cnstats", "China Statistics")
    sess2 = db.get_session()
    fn = DaasFunction(source_id=cn["id"], name="cnstats_gdp", category="Macro",
                      output_type="DataFrame")
    sess2.add(fn)
    sess2.commit()
    sess2.add(DaasFunctionColumn(function_id=fn.id, name="gdp", type="float",
                                 description="GDP in CNY"))
    sess2.commit()

    # Upsert entity (stock) directly via session — sync script does this too
    apple = Entity(entity_type="stock", code="AAPL", name="Apple Inc.",
                   ticker="AAPL", exchange="NASDAQ", country_code="US")
    sess2.add(apple)
    sess2.commit()
    # Idempotent upsert on (entity_type, code): a second insert is rejected
    from sqlalchemy.exc import IntegrityError as _IE
    try:
        sess2.add(Entity(entity_type="stock", code="AAPL", name="Apple Inc."))
        sess2.commit()
        assert False, "dup (entity_type, code) should reject"
    except _IE:
        sess2.rollback()
    assert sess2.query(Entity).filter_by(entity_type="stock", code="AAPL").count() == 1, "entity unique"

    # search_entities — by name, ticker, code
    assert any(r["code"] == "AAPL" for r in s.search_entities("Apple")), "search by name"
    assert any(r["code"] == "AAPL" for r in s.search_entities("AAPL")), "search by ticker"
    assert any(r["code"] == "AAPL" for r in s.search_entities("AAPL", entity_type="stock")), "search with type filter"
    assert s.search_entities("zzznope") == [], "no matches returns []"

    # get_entity
    assert s.get_entity(apple.id)["code"] == "AAPL", "get_entity"
    assert s.get_entity(999999) is None, "get_entity missing → None"

    # list_entities pagination + filter
    listed = s.list_entities(entity_type="stock", limit=10)
    assert listed["count"] == 1 and listed["total"] == 1, "list_entities"

    # link entity → yfinance (external-MCP) and → cnstats (daas-registered)
    lk1 = s.link_entity_datasource(apple.id, "yfinance", identifier_in_source="AAPL")
    assert lk1["identifier_in_source"] == "AAPL", "link created"
    lk2 = s.link_entity_datasource(apple.id, "cnstats", identifier_in_source="CN")
    # upsert: re-link yfinance with new identifier
    s.link_entity_datasource(apple.id, "yfinance", identifier_in_source="AAPL", coverage="partial")
    assert sess2.query(EntityDatasourceLink).filter_by(entity_id=apple.id).count() == 2, "two links"
    # unknown source rejected
    try:
        s.link_entity_datasource(apple.id, "nope")
        assert False, "unknown source should reject"
    except ValueError:
        pass

    # get_entity_coverage — external-MCP source → column_hint; prefilled instruction
    cov = s.get_entity_coverage(apple.id)
    assert cov["count"] == 2, "coverage count"
    yf_cov = next(d for d in cov["datasources"] if d["source"] == "yfinance")
    assert yf_cov["identifier_in_source"] == "AAPL", "coverage identifier"
    assert yf_cov["column_count"] == 0, "yfinance has no daas_functions"
    assert "column_hint" in yf_cov and yf_cov["column_hint"]["tool"] == "call_yfinance_function", "column_hint"
    pf = yf_cov["sections"][0]["prefilled_instruction"]
    assert "param=name=ticker_history" in pf and "param=params_json=<ask-agent>" in pf, "only identifier param prefilled"
    assert "param=name=ticker_history" in pf, "name param not identifier-keyed, left as-is"
    cn_cov = next(d for d in cov["datasources"] if d["source"] == "cnstats")
    assert cn_cov["column_count"] == 1 and cn_cov["columns"][0]["name"] == "gdp", "daas columns resolved"
    assert "column_hint" not in cn_cov, "no hint when columns exist"

    # entity with no links → empty coverage
    lonely = Entity(entity_type="country", code="US", name="United States")
    sess2.add(lonely)
    sess2.commit()
    assert s.get_entity_coverage(lonely.id)["count"] == 0, "empty coverage"

    # unlink
    s.unlink_entity_datasource(apple.id, "yfinance")
    assert sess2.query(EntityDatasourceLink).filter_by(entity_id=apple.id).count() == 1, "unlink"
    try:
        s.unlink_entity_datasource(apple.id, "yfinance")
        assert False, "unlink missing should reject"
    except ValueError:
        pass

    # cascade: delete entity → links gone
    sess2.expire_all()
    apple = sess2.get(Entity, apple.id)
    sess2.delete(apple)
    sess2.commit()
    assert sess2.query(EntityDatasourceLink).filter_by(entity_id=apple.id).count() == 0, "cascade on entity delete"

    # ---- Existing read API still works ----
    assert callable(s.list_sources), "list_sources still present"
    assert callable(s.list_categories), "list_categories still present"

    print("ALL SELFCHECK ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
