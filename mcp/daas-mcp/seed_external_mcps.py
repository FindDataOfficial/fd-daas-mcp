"""Seed external MCPs (edgar, edinet, yfinance, cnstats) as daas datasources.

Idempotent: re-runnable on the live `daas.db`. Safe to invoke from CI or after
a fresh schema create. `--unseed` removes only rows this script owns; never
touches the pre-existing `ckan`/`cnstats`/`worldbank` rows themselves (only
the forms/sections/categories *this seed* created under them).

Section `instruction` strings follow a tiny routing grammar so an agent can
deterministically dispatch to the right sibling MCP:

    mcp=<mcp-name> tool=<tool-name> [param=<key>=<value>]*

For parameters the agent must supply, the value is the literal `<ask-agent>`.

Usage:
    uv run python mcp/daas-mcp/seed_external_mcps.py              # seed
    uv run python mcp/daas-mcp/seed_external_mcps.py --dry-run    # plan only
    uv run python mcp/daas-mcp/seed_external_mcps.py --unseed     # rollback

ponytail: seed data is hard-coded constants; no sibling-MCP imports at
runtime, so the script runs in the daas-mcp venv with no extra deps.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parent.parent.parent  # mcp/daas-mcp/ → mcp/ → repo root
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

sys.path.insert(0, str(_THIS.parent))

from daas_database import Database
from models import (
    Category,
    DaasSource,
    DatasourceCollection,
    DatasourceCollectionItem,
    DatasourceForm,
    DatasourceSection,
)


# ════════════════════════════════════════════════════════════════════════
# Routing grammar validator
# ════════════════════════════════════════════════════════════════════════

_ROUTING_RE = re.compile(r"^mcp=\S+\s+tool=\S+(\s+param=[^=\s]+=\S+)*$")


def validate_routing(instruction: str) -> None:
    """Raise ValueError if instruction doesn't match the routing grammar."""
    if not _ROUTING_RE.match(instruction):
        raise ValueError(f"Malformed routing instruction: {instruction!r}")


# ════════════════════════════════════════════════════════════════════════
# SEED_MARKER — natural keys this seed owns. `--unseed` deletes exactly these.
# ════════════════════════════════════════════════════════════════════════

# Two-level category tree, roots first then leaves (insertion order matters).
CATEGORIES: list[tuple[str, str, str | None]] = [
    # (name, label, parent_name)
    ("Filings", "Filings", None),
    ("Market-Data", "Market Data", None),
    ("Macro", "Macro Indicators", None),
    ("US-SEC", "US SEC EDGAR", "Filings"),
    ("JP-EDINET", "Japan EDINET", "Filings"),
    ("CN-Cninfo", "China Cninfo", "Filings"),
    ("HK-HKEX", "Hong Kong HKEXnews", "Filings"),
    ("Global", "Global Markets", "Market-Data"),
    ("China", "China Statistics", "Macro"),
]

# Sources this seed may CREATE and DELETE. cnstats is enriched, never deleted.
OWNED_SOURCES = ("edgar", "edinet", "yfinance", "cnreport", "hkex")
ENRICH_SOURCES = ("cnstats",)
# Hard guard: these source names are NEVER deleted by --unseed, regardless.
PROTECTED_SOURCES = {"ckan", "cnstats", "worldbank"}

SOURCES: dict[str, dict] = {
    "edgar": {
        "label": "SEC EDGAR",
        "description": "US Securities and Exchange Commission filings (10-K, 10-Q, 8-K, Form 4) via edgartools-mcp.",
        "url": "https://www.sec.gov/edgar",
        "category": "US-SEC",
    },
    "edinet": {
        "label": "Japan EDINET",
        "description": "Japan FSA EDINET corporate disclosure system (有価証券報告書 and related forms) via edinet-mcp.",
        "url": "https://disclosure.edinet-fsa.go.jp/",
        "category": "JP-EDINET",
    },
    "yfinance": {
        "label": "Yahoo Finance",
        "description": "Global market data via yfinance-mcp — prices, fundamentals, options, holders, news.",
        "url": "https://finance.yahoo.com/",
        "category": "Global",
    },
    "cnstats": {
        # Pre-existing row — DO NOT overwrite label/description/url.
        "label": None,
        "description": None,
        "url": None,
        "category": "China",
    },
    "cnreport": {
        "label": "Chinese Annual Reports",
        "description": "A-share 年度报告 (annual reports) via cnreport-mcp — outline extraction, section text retrieval, LLM structured extraction, and Elasticsearch search.",
        "url": "http://www.cninfo.com.cn/",
        "category": "CN-Cninfo",
    },
    "hkex": {
        "label": "Hong Kong Stock Exchange (HKEXnews + akshare)",
        "description": "HK-listed company filings, financials, and disclosure calendar via hkreport-mcp.",
        "url": "https://www1.hkexnews.hk",
        "category": "HK-HKEX",
    },
}

# ── EDGAR forms + sections ─────────────────────────────────────────────
# Form set chosen per design Decision 5: keep filings as forms; route
# `Financials` and `Insider-Trades` as extra forms (vs sections) so the
# instruction is at form-level and stays consistent across the seed.
EDGAR_FORMS: dict[str, str] = {
    "10-K": "Annual report (Form 10-K)",
    "10-Q": "Quarterly report (Form 10-Q)",
    "8-K": "Current report (Form 8-K)",
    "4": "Insider transaction (Form 4)",
    "Financials": "Standardized financial statements (XBRL-derived)",
    "Insider-Trades": "Aggregated insider transactions",
}

_EDGAR_10K_BASE = "mcp=edgartools-mcp tool=get_filing param=form=10-K param=ticker_or_cik=<ask-agent> param=detail=full"
_EDGAR_10Q_BASE = "mcp=edgartools-mcp tool=get_filing param=form=10-Q param=ticker_or_cik=<ask-agent> param=detail=full"
_EDGAR_8K_BASE = "mcp=edgartools-mcp tool=get_filing param=form=8-K param=ticker_or_cik=<ask-agent>"

EDGAR_SECTIONS: dict[str, list[tuple[str, str]]] = {
    "10-K": [
        ("Item 1 Business", _EDGAR_10K_BASE),
        ("Item 1A Risk Factors", _EDGAR_10K_BASE),
        ("Item 7 MD&A", _EDGAR_10K_BASE),
        ("Item 7A Quantitative and Qualitative Disclosures About Market Risk", _EDGAR_10K_BASE),
        ("Item 8 Financial Statements and Supplementary Data", _EDGAR_10K_BASE),
    ],
    "10-Q": [
        ("Item 1 Financial Statements", _EDGAR_10Q_BASE),
        ("Item 2 MD&A", _EDGAR_10Q_BASE),
    ],
    "8-K": [
        ("Item 1.01 Entry into a Material Definitive Agreement", _EDGAR_8K_BASE),
        ("Item 2.02 Results of Operations and Financial Condition", _EDGAR_8K_BASE),
        ("Item 5.02 Departure of Directors or Officers", _EDGAR_8K_BASE),
        ("Item 8.01 Other Events", _EDGAR_8K_BASE),
    ],
    "4": [
        ("Transactions", "mcp=edgartools-mcp tool=get_insider_trades param=ticker_or_cik=<ask-agent>"),
    ],
    "Financials": [
        ("Income Statement", "mcp=edgartools-mcp tool=get_financials param=ticker_or_cik=<ask-agent> param=statement=income_statement"),
        ("Balance Sheet", "mcp=edgartools-mcp tool=get_financials param=ticker_or_cik=<ask-agent> param=statement=balance_sheet"),
        ("Cash Flow", "mcp=edgartools-mcp tool=get_financials param=ticker_or_cik=<ask-agent> param=statement=cashflow"),
    ],
    "Insider-Trades": [
        ("Recent Form 4 Filings", "mcp=edgartools-mcp tool=get_insider_trades param=ticker_or_cik=<ask-agent>"),
    ],
}

# ── EDINET forms (doc-type codes) + sections ───────────────────────────
EDINET_FORMS: dict[str, str] = {
    "120": "有価証券報告書 (Annual Securities Report)",
    "130": "四半期報告書 (Quarterly Report)",
    "140": "半期報告書 (Semi-annual Report)",
    "150": "臨時報告書 (Extraordinary Report)",
    "160": "訂正届出書 (Amendment Report)",
    "170": "自己株式取得状況 (Share Buyback Status)",
    "180": "親会社等状況報告書 (Parent Company Status Report)",
    "350": "大量保有報告書 (Large Shareholding Report)",
    "360": "公開買付届出書 (Tender Offer Statement)",
}


def edinet_sections_for(form_type: str) -> list[tuple[str, str]]:
    """All EDINET forms get a `Document` section; form 120 also gets Listing + Lookup."""
    secs = [
        (
            "Document",
            f"mcp=edinet-mcp tool=get_document param=doc_id=<ask-agent> param=doc_type_code={form_type}",
        ),
    ]
    if form_type == "120":
        secs.append((
            "Listing",
            f"mcp=edinet-mcp tool=list_documents param=date=<ask-agent> param=doc_type={form_type}",
        ))
        secs.append((
            "Lookup",
            "mcp=edinet-mcp tool=get_entity param=ticker_or_code=<ask-agent>",
        ))
    return secs


# ── yfinance + cnstats: single `default` form, sections group tools ────
YFINANCE_SECTIONS: list[tuple[str, str]] = [
    # (section_name, representative function name) — instruction built at seed time
    ("Search", "search"),
    ("Download", "download"),
    ("Price-History", "ticker_history"),
    ("Fundamentals", "ticker_info"),
    ("Options", "ticker_option_chain"),
    ("Holders", "ticker_major_holders"),
    ("News", "ticker_news"),
]

CNSTATS_SECTIONS: list[tuple[str, str]] = [
    ("Search", "mcp=cnstats-mcp tool=search_functions param=query=<ask-agent>"),
    ("Function-Info", "mcp=cnstats-mcp tool=get_function_info param=name=<ask-agent>"),
    ("Categories", "mcp=cnstats-mcp tool=list_categories"),
    ("Call", "mcp=cnstats-mcp tool=call_cnstats_function param=name=<ask-agent> param=params_json=<ask-agent>"),
]

# ── cnreport: single `Annual-Report` form, one section per CSRC 年报 节 ──
CNREPORT_FORMS: dict[str, str] = {
    "Annual-Report": "年度报告 (A-share Annual Report)",
}# Selector text is pre-bound; agent supplies `source` (report URL or local path).
# extract_section's resolve_selector falls back to regex search, so the title
# alone matches body headings like `第三节 管理层讨论与分析` too.
_CNREPORT_TOOL = "mcp=cnreport-mcp tool=extract_section param=source=<ask-agent>"
CNREPORT_SECTIONS: list[tuple[str, str]] = [
    ("重要提示、目录及释义", f"{_CNREPORT_TOOL} param=selector=重要提示"),
    ("公司简介和主要财务指标", f"{_CNREPORT_TOOL} param=selector=公司简介和主要财务指标"),
    ("管理层讨论与分析", f"{_CNREPORT_TOOL} param=selector=管理层讨论与分析"),
    ("公司治理", f"{_CNREPORT_TOOL} param=selector=公司治理"),
    ("环境与社会责任", f"{_CNREPORT_TOOL} param=selector=环境与社会责任"),
    ("重要事项", f"{_CNREPORT_TOOL} param=selector=重要事项"),
    ("股份变动及股东情况", f"{_CNREPORT_TOOL} param=selector=股份变动及股东情况"),
    ("财务报告", f"{_CNREPORT_TOOL} param=selector=财务报告"),
    ("其他报告", f"{_CNREPORT_TOOL} param=selector=其他报告"),
]

# ── hkex: five forms, one section each, all routed to hkreport-mcp ─────
HKEX_FORMS: dict[str, str] = {
    "Annual Report": "Annual Report (HKEX-listed company)",
    "Interim Report": "Interim Report (HKEX-listed company)",
    "Announcement": "General HKEXnews announcement",
    "Financials": "Standardized HK financial statements (akshare-derived)",
    "Calendar": "Upcoming results-announcement and AGM dates",
}

HKEX_SECTIONS: dict[str, list[tuple[str, str]]] = {
    "Annual Report": [
        ("Filings", "mcp=hkreport-mcp tool=list_filings param=ticker_or_name=<ask-agent> param=form=Annual_Report"),
    ],
    "Interim Report": [
        ("Filings", "mcp=hkreport-mcp tool=list_filings param=ticker_or_name=<ask-agent> param=form=Interim_Report"),
    ],
    "Announcement": [
        ("Lookup", "mcp=hkreport-mcp tool=get_company param=ticker_or_name=<ask-agent>"),
        ("Document", "mcp=hkreport-mcp tool=get_filing param=doc_id_or_url=<ask-agent>"),
    ],
    "Financials": [
        ("Income Statement", "mcp=hkreport-mcp tool=get_financials param=ticker_or_name=<ask-agent> param=statement=income_statement"),
        ("Balance Sheet", "mcp=hkreport-mcp tool=get_financials param=ticker_or_name=<ask-agent> param=statement=balance_sheet"),
        ("Cash Flow", "mcp=hkreport-mcp tool=get_financials param=ticker_or_name=<ask-agent> param=statement=cashflow"),
    ],
    "Calendar": [
        ("Upcoming", "mcp=hkreport-mcp tool=get_disclosure_calendar param=ticker_or_name=<ask-agent>"),
    ],
}

# ── Core collection ────────────────────────────────────────────────────
CORE_COLLECTION = "core"
CORE_COLLECTION_DESC = "Baseline cross-MCP view spanning edgar, edinet, yfinance, cnstats, cnreport, hkex."
CORE_ITEMS: list[tuple[str, str]] = [
    # (source_name, section_name) — must resolve uniquely under source
    ("edgar", "Item 1A Risk Factors"),
    ("edgar", "Item 7 MD&A"),
    ("edinet", "Listing"),       # under form 120
    ("yfinance", "Price-History"),
    ("yfinance", "Fundamentals"),
    ("cnstats", "Categories"),
    ("cnreport", "管理层讨论与分析"),
    ("hkex", "Income Statement"),
]


# ════════════════════════════════════════════════════════════════════════
# Counters
# ════════════════════════════════════════════════════════════════════════

class Counts:
    def __init__(self) -> None:
        self.sources_new = 0
        self.sources_updated = 0
        self.categories_new = 0
        self.forms_new = 0
        self.sections_new = 0
        self.sections_updated = 0
        self.collections_new = 0
        self.collection_items_new = 0
        self.deleted: dict[str, int] = {
            "sources": 0, "categories": 0, "forms": 0,
            "sections": 0, "collections": 0, "collection_items": 0,
        }

    def print_seed_summary(self) -> None:
        print(f"  sources         +{self.sources_new} (~{self.sources_updated} updated)")
        print(f"  categories      +{self.categories_new}")
        print(f"  forms           +{self.forms_new}")
        print(f"  sections        +{self.sections_new} (~{self.sections_updated} updated)")
        print(f"  collections     +{self.collections_new}")
        print(f"  collection_items +{self.collection_items_new}")

    def print_unseed_summary(self) -> None:
        for k, v in self.deleted.items():
            print(f"  {k:<17} -{v}")


# ════════════════════════════════════════════════════════════════════════
# get-or-create helpers — natural-key lookup, then create or update-if-diff
# ════════════════════════════════════════════════════════════════════════

def goc_category(session, name, label, parent_id, counts, dry_run):
    cat = session.query(Category).filter(Category.name == name).first()
    if cat is not None:
        return cat
    if dry_run:
        print(f"  [plan] CREATE category name={name} parent_id={parent_id}")
        return None
    cat = Category(name=name, label=label, parent_id=parent_id)
    session.add(cat)
    session.commit()
    counts.categories_new += 1
    return cat


def goc_source(session, name, info, category_id, counts, dry_run):
    src = session.query(DaasSource).filter(DaasSource.name == name).first()
    if src is not None:
        changed = False
        # For sources we own, sync label/description/url. For enriched sources
        # (cnstats) skip those — info values are None there anyway.
        if name in OWNED_SOURCES:
            if info["label"] and src.label != info["label"]:
                src.label = info["label"]
                changed = True
            if info["description"] and src.description != info["description"]:
                src.description = info["description"]
                changed = True
            if info["url"] and src.url != info["url"]:
                src.url = info["url"]
                changed = True
        # category_id sync for both owned and enriched sources
        if src.category_id != category_id:
            src.category_id = category_id
            changed = True
        if changed:
            if dry_run:
                print(f"  [plan] UPDATE source name={name}")
            else:
                session.commit()
                counts.sources_updated += 1
        return src
    if dry_run:
        print(f"  [plan] CREATE source name={name}")
        return None
    src = DaasSource(
        name=name,
        label=info["label"] or name,
        description=info["description"],
        url=info["url"],
        category_id=category_id,
        enabled=True,
    )
    session.add(src)
    session.commit()
    counts.sources_new += 1
    return src


def goc_form(session, source_id, form_type, label, counts, dry_run):
    form = (
        session.query(DatasourceForm)
        .filter(DatasourceForm.source_id == source_id,
                DatasourceForm.form_type == form_type)
        .first()
    )
    if form is not None:
        if label and form.label != label:
            form.label = label
            if not dry_run:
                session.commit()
        return form
    if dry_run:
        print(f"  [plan] CREATE form source_id={source_id} form_type={form_type}")
        return None
    form = DatasourceForm(source_id=source_id, form_type=form_type, label=label)
    session.add(form)
    session.commit()
    counts.forms_new += 1
    return form


def goc_section(session, form_id, name, instruction, counts, dry_run):
    validate_routing(instruction)  # fail fast on typos in the seed source
    sec = (
        session.query(DatasourceSection)
        .filter(DatasourceSection.form_id == form_id,
                DatasourceSection.section_name == name)
        .first()
    )
    if sec is not None:
        if sec.instruction != instruction:
            if dry_run:
                print(f"  [plan] UPDATE section form_id={form_id} name={name!r}")
            else:
                sec.instruction = instruction
                session.commit()
                counts.sections_updated += 1
        return sec
    if dry_run:
        print(f"  [plan] CREATE section form_id={form_id} name={name!r}")
        return None
    sec = DatasourceSection(form_id=form_id, section_name=name, instruction=instruction)
    session.add(sec)
    session.commit()
    counts.sections_new += 1
    return sec


def goc_collection(session, name, description, counts, dry_run):
    coll = session.query(DatasourceCollection).filter(
        DatasourceCollection.name == name).first()
    if coll is not None:
        return coll
    if dry_run:
        print(f"  [plan] CREATE collection name={name}")
        return None
    coll = DatasourceCollection(name=name, description=description)
    session.add(coll)
    session.commit()
    counts.collections_new += 1
    return coll


def goc_collection_item(session, collection_id, source_id, section_id, counts, dry_run):
    item = (
        session.query(DatasourceCollectionItem)
        .filter(
            DatasourceCollectionItem.collection_id == collection_id,
            DatasourceCollectionItem.source_id == source_id,
            DatasourceCollectionItem.section_id == section_id,
        )
        .first()
    )
    if item is not None:
        return item
    if dry_run:
        print(f"  [plan] CREATE collection_item coll={collection_id} "
              f"src={source_id} sec={section_id}")
        return None
    item = DatasourceCollectionItem(
        collection_id=collection_id, source_id=source_id, section_id=section_id)
    session.add(item)
    session.commit()
    counts.collection_items_new += 1
    return item


# ════════════════════════════════════════════════════════════════════════
# Seed
# ════════════════════════════════════════════════════════════════════════

def seed(session, counts: Counts, dry_run: bool = False) -> None:
    # ── 1. Categories ──
    cat_id: dict[str, int | None] = {}
    for name, label, parent_name in CATEGORIES:
        parent_id = cat_id.get(parent_name) if parent_name else None
        cat = goc_category(session, name, label, parent_id, counts, dry_run)
        cat_id[name] = cat.id if cat is not None else None

    # ── 2. Sources ──
    src_id: dict[str, int | None] = {}
    for src_name in ("edgar", "edinet", "yfinance", "cnstats", "cnreport", "hkex"):
        info = SOURCES[src_name]
        category_id = cat_id[info["category"]]
        src = goc_source(session, src_name, info, category_id, counts, dry_run)
        src_id[src_name] = src.id if src is not None else None

    if dry_run:
        # Without IDs, downstream writes can't be enumerated meaningfully.
        # Report counts and stop.
        print("  [plan] (forms/sections/collection writes elided in dry-run)")
        return

    # ── 3. EDGAR forms + sections ──
    for form_type, form_label in EDGAR_FORMS.items():
        form = goc_form(session, src_id["edgar"], form_type, form_label, counts, dry_run)
        for sec_name, instr in EDGAR_SECTIONS[form_type]:
            goc_section(session, form.id, sec_name, instr, counts, dry_run)

    # ── 4. EDINET forms + sections ──
    for form_type, form_label in EDINET_FORMS.items():
        form = goc_form(session, src_id["edinet"], form_type, form_label, counts, dry_run)
        for sec_name, instr in edinet_sections_for(form_type):
            goc_section(session, form.id, sec_name, instr, counts, dry_run)

    # ── 5. yfinance default form ──
    yf_form = goc_form(session, src_id["yfinance"], "default",
                       "Yahoo Finance tool catalog", counts, dry_run)
    for sec_name, fn_name in YFINANCE_SECTIONS:
        instr = (
            f"mcp=yfinance-mcp tool=call_yfinance_function "
            f"param=name={fn_name} param=params_json=<ask-agent>"
        )
        goc_section(session, yf_form.id, sec_name, instr, counts, dry_run)

    # ── 6. cnstats default form ──
    cn_form = goc_form(session, src_id["cnstats"], "default",
                       "CNStats tool catalog", counts, dry_run)
    for sec_name, instr in CNSTATS_SECTIONS:
        goc_section(session, cn_form.id, sec_name, instr, counts, dry_run)

    # ── 7. cnreport Annual-Report form ──
    for form_type, form_label in CNREPORT_FORMS.items():
        form = goc_form(session, src_id["cnreport"], form_type, form_label, counts, dry_run)
        for sec_name, instr in CNREPORT_SECTIONS:
            goc_section(session, form.id, sec_name, instr, counts, dry_run)

    # ── 7b. hkex forms + sections ──
    for form_type, form_label in HKEX_FORMS.items():
        form = goc_form(session, src_id["hkex"], form_type, form_label, counts, dry_run)
        for sec_name, instr in HKEX_SECTIONS[form_type]:
            goc_section(session, form.id, sec_name, instr, counts, dry_run)

    # ── 8. Core collection ──
    coll = goc_collection(session, CORE_COLLECTION, CORE_COLLECTION_DESC, counts, dry_run)
    for src_name, sec_name in CORE_ITEMS:
        sid = src_id[src_name]
        sec = (
            session.query(DatasourceSection)
            .join(DatasourceForm)
            .filter(DatasourceForm.source_id == sid,
                    DatasourceSection.section_name == sec_name)
            .first()
        )
        if sec is None:
            raise RuntimeError(
                f"Core item ({src_name}, {sec_name}) did not resolve — seed bug")
        goc_collection_item(session, coll.id, sid, sec.id, counts, dry_run)


# ════════════════════════════════════════════════════════════════════════
# Unseed — remove only rows this seed owns
# ════════════════════════════════════════════════════════════════════════

def unseed(session, counts: Counts) -> None:
    our_cat_names = {n for n, _, _ in CATEGORIES}

    # 1. Core collection items + collection
    coll = session.query(DatasourceCollection).filter(
        DatasourceCollection.name == CORE_COLLECTION).first()
    if coll is not None:
        items = session.query(DatasourceCollectionItem).filter(
            DatasourceCollectionItem.collection_id == coll.id).all()
        for it in items:
            session.delete(it)
            counts.deleted["collection_items"] += 1
        session.delete(coll)
        counts.deleted["collections"] += 1
        session.commit()

    # 2. Owned sources (edgar/edinet/yfinance) — cascade kills forms+sections,
    #    but we count them explicitly before delete for the summary.
    for name in OWNED_SOURCES:
        if name in PROTECTED_SOURCES:
            continue  # belt-and-braces; OWNED_SOURCES never contains these
        src = session.query(DaasSource).filter(DaasSource.name == name).first()
        if src is None:
            continue
        forms = session.query(DatasourceForm).filter(
            DatasourceForm.source_id == src.id).all()
        for form in forms:
            sec_n = session.query(DatasourceSection).filter(
                DatasourceSection.form_id == form.id).count()
            counts.deleted["sections"] += sec_n
            counts.deleted["forms"] += 1
        session.delete(src)
        counts.deleted["sources"] += 1
        session.commit()

    # 3. Enrich sources (cnstats): delete only the `default` form + its sections
    #    we created. Null out category_id only if it points at one of our cats.
    for name in ENRICH_SOURCES:
        src = session.query(DaasSource).filter(DaasSource.name == name).first()
        if src is None:
            continue
        form = session.query(DatasourceForm).filter(
            DatasourceForm.source_id == src.id,
            DatasourceForm.form_type == "default",
        ).first()
        if form is not None:
            secs = session.query(DatasourceSection).filter(
                DatasourceSection.form_id == form.id).all()
            for s in secs:
                session.delete(s)
                counts.deleted["sections"] += 1
            session.delete(form)
            counts.deleted["forms"] += 1
        if src.category_id is not None:
            cat = session.get(Category, src.category_id)
            if cat is not None and cat.name in our_cat_names:
                src.category_id = None
        session.commit()

    # 4. Categories — leaves first, roots last. Skip any still referenced
    #    by a datasource (shouldn't happen given steps 2+3, but be safe).
    for name in reversed([n for n, _, _ in CATEGORIES]):
        cat = session.query(Category).filter(Category.name == name).first()
        if cat is None:
            continue
        ref_n = session.query(DaasSource).filter(
            DaasSource.category_id == cat.id).count()
        if ref_n:
            print(f"  skipping category {name}: still referenced by {ref_n} datasource(s)")
            continue
        session.delete(cat)
        counts.deleted["categories"] += 1
    session.commit()


# ════════════════════════════════════════════════════════════════════════
# Entrypoint
# ════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Seed external MCPs (edgar/edinet/yfinance/cnstats) as daas datasources.")
    p.add_argument("--db-url", help="Override DAAS_DATABASE_URL for this run")
    p.add_argument("--unseed", action="store_true",
                   help="Remove only rows this seed owns")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the plan; perform no writes")
    args = p.parse_args(argv)

    if args.db_url:
        os.environ["DAAS_DATABASE_URL"] = args.db_url

    # Reset Database singleton so a --db-url override actually takes effect
    Database._instance = None
    db = Database()
    session = db.get_session()
    counts = Counts()

    if args.unseed:
        print("Unseeding external MCP datasources...")
        unseed(session, counts)
        counts.print_unseed_summary()
        print("Done.")
    elif args.dry_run:
        print("Dry-run plan (no writes):")
        seed(session, counts, dry_run=True)
        counts.print_seed_summary()
    else:
        print("Seeding external MCP datasources...")
        seed(session, counts, dry_run=False)
        counts.print_seed_summary()
        print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
