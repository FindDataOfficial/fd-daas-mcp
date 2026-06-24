#!/usr/bin/env python3
"""
Populate mcp/daas.db with source, function, and column metadata
from the three source adapters: ckan, cnstats, worldbank.

Run from mcp/ directory:
    python3 populate_daas.py
"""
from __future__ import annotations

import os
import sys

# Ensure the harness package is importable
_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
_HARNESS_ROOT = os.path.join(os.path.dirname(_MCP_DIR), "daas-agent-harness")
if _HARNESS_ROOT not in sys.path:
    sys.path.insert(0, _HARNESS_ROOT)

from cli_anything.daas.sources.ckan_source import CKANAdapter, CKAN_FUNCTIONS
from cli_anything.daas.sources.cnstats_source import CNStatsAdapter, CNSTATS_FUNCTIONS
from cli_anything.daas.sources.worldbank_source import WorldBankAdapter, KEY_INDICATORS


def build_worldbank_functions():
    """Build function dicts from WorldBank KEY_INDICATORS."""
    result = []
    for code, desc, category in KEY_INDICATORS:
        name = f"worldbank_{code.lower().replace('.', '_')}"
        result.append({
            "name": name,
            "label": desc,
            "description": f"World Bank: {desc} (indicator: {code})",
            "category": category,
            "source": "worldbank",
            "parameters": [
                {"name": "country", "type": "str", "required": False,
                 "description": "ISO 3-letter country code (e.g., CHN, USA) or 'all'"},
                {"name": "time", "type": "str", "required": False,
                 "description": "Year or range (e.g., 2020 or 2015:2023)"},
            ],
            "columns": [
                {"name": "country", "type": "str", "description": "Country name"},
                {"name": "iso3", "type": "str", "description": "ISO 3-letter code"},
                {"name": "year", "type": "str", "description": "Year"},
                {"name": "value", "type": "float64", "description": desc},
            ],
        })
    return result


SOURCE_DEFS = {
    "ckan": {
        "label": "CKAN Open Data",
        "description": "Open data portals (data.gov, data.gov.uk, etc.) — configurable portal URL",
        "url": "https://data.gov/",
        "functions": CKAN_FUNCTIONS,
    },
    "cnstats": {
        "label": "Chinese Statistics",
        "description": "National Bureau of Statistics macro indicators — CPI, PMI, industrial output, retail sales",
        "url": "https://data.stats.gov.cn/",
        "functions": CNSTATS_FUNCTIONS,
    },
    "worldbank": {
        "label": "World Bank",
        "description": "World Bank Open Data — GDP, population, trade, education, health (1400+ indicators)",
        "url": "https://data.worldbank.org/",
        "functions": build_worldbank_functions(),
    },
}


def main():
    db_path = os.environ.get("DAAS_DATABASE_URL", "sqlite:///daas.db")
    # Strip sqlite:/// prefix to get file path
    if db_path.startswith("sqlite:///"):
        db_file = db_path[len("sqlite:///"):]
        if not os.path.isabs(db_file):
            db_file = os.path.join(_MCP_DIR, db_file)
    else:
        db_file = os.path.join(_MCP_DIR, "daas.db")
        db_path = f"sqlite:///{db_file}"

    print(f"Database: {db_path}")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session
    from cli_anything.daas.core.models import Base, Source, Function, FunctionColumn

    engine = create_engine(db_path, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    total_funcs = 0
    total_cols = 0

    try:
        for source_name, src_info in SOURCE_DEFS.items():
            print(f"\n[{source_name}] {src_info['label']}")

            # Upsert source
            existing = session.query(Source).filter(Source.name == source_name).first()
            if existing:
                existing.label = src_info["label"]
                existing.description = src_info["description"]
                existing.url = src_info["url"]
            else:
                session.add(Source(
                    name=source_name,
                    label=src_info["label"],
                    description=src_info["description"],
                    url=src_info["url"],
                    enabled=True,
                ))
            session.flush()
            source_obj = session.query(Source).filter(Source.name == source_name).first()

            funcs = src_info["functions"]
            print(f"  Functions: {len(funcs)}")

            for fdata in funcs:
                fname = fdata.get("name", "")
                if not fname:
                    continue

                # Upsert function
                existing_func = (
                    session.query(Function)
                    .filter(Function.source_id == source_obj.id, Function.name == fname)
                    .first()
                )
                if existing_func:
                    existing_func.label = fdata.get("label", fname)
                    existing_func.description = fdata.get("description", "")
                    existing_func.category = fdata.get("category", "未分类")
                    existing_func.parameters = fdata.get("parameters", [])
                else:
                    session.add(Function(
                        source_id=source_obj.id,
                        name=fname,
                        label=fdata.get("label", fname),
                        description=fdata.get("description", ""),
                        category=fdata.get("category", "未分类"),
                        parameters=fdata.get("parameters", []),
                        output_type="DataFrame",
                    ))
                session.flush()
                func_obj = (
                    session.query(Function)
                    .filter(Function.source_id == source_obj.id, Function.name == fname)
                    .first()
                )
                total_funcs += 1

                # Upsert columns
                columns = fdata.get("columns", [])
                for coldata in columns:
                    cname = coldata.get("name", "")
                    if not cname:
                        continue
                    existing_col = (
                        session.query(FunctionColumn)
                        .filter(FunctionColumn.function_id == func_obj.id, FunctionColumn.name == cname)
                        .first()
                    )
                    if existing_col:
                        existing_col.label = coldata.get("label", cname)
                        existing_col.type = coldata.get("type", "str")
                        existing_col.description = coldata.get("description", "")
                    else:
                        session.add(FunctionColumn(
                            function_id=func_obj.id,
                            name=cname,
                            label=coldata.get("label", cname),
                            type=coldata.get("type", "str"),
                            description=coldata.get("description", ""),
                            nullable=True,
                        ))
                    total_cols += 1

        session.commit()
        print(f"\nDone. {total_funcs} functions, {total_cols} columns committed to {db_file}")

        # Print summary
        for source_name in SOURCE_DEFS:
            src = session.query(Source).filter(Source.name == source_name).first()
            if src:
                cnt = session.query(Function).filter(Function.source_id == src.id).count()
                col_cnt = (
                    session.query(FunctionColumn)
                    .join(Function)
                    .filter(Function.source_id == src.id)
                    .count()
                )
                print(f"  {source_name}: {cnt} functions, {col_cnt} columns")

    finally:
        session.close()


if __name__ == "__main__":
    main()
