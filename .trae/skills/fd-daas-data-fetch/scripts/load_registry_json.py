#!/usr/bin/env python3
"""Load a registry JSON file (datasource + functions + entities + indicator
rules) into the daas database defined by DAAS_DATABASE_URL in the .env file.

Idempotent: existing rows are updated in place; missing rows are created.
This is what `fd-daas-data-fetch` runs to ensure a datasource exists in the
DB before fetching — if the datasource is missing, it (and its functions,
entities, links, indicator rules) is added.

Run via the daas-mcp env so the models + Database singleton resolve:

    uv run --directory mcp/daas-mcp python <this_script> <registry.json> [--env .env] [--dry-run]

The DB URL is read from DAAS_DATABASE_URL (root .env, default sqlite:///mcp/daas.db).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# --- make daas-mcp + models importable regardless of cwd ----------------
# Script lives at <repo>/.trae/skills/fd-daas-data-fetch/scripts/load_registry_json.py
# `models` is a package at mcp/models, so its PARENT (mcp/) must be on sys.path;
# `daas_database` is a py-module at mcp/daas-mcp, so that dir must be on sys.path.
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[4]  # scripts/ -> skill -> skills -> .trae -> repo
for _p in (_REPO_ROOT / "mcp" / "daas-mcp", _REPO_ROOT / "mcp"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dotenv import load_dotenv  # noqa: E402

from daas_database import get_database  # noqa: E402
from models.models import (  # noqa: E402
    DaasSource,
    DaasFunction,
    DaasFunctionColumn,
    Entity,
    EntityDatasourceLink,
    IndicatorRule,
)


def _load_env(env_file: str | None) -> None:
    """Load DAAS_DATABASE_URL from the repo root .env (or an explicit --env)."""
    candidates = []
    if env_file:
        candidates.append(Path(env_file))
    candidates.append(_REPO_ROOT / ".env")
    candidates.append(_REPO_ROOT / "mcp" / "daas-mcp" / ".env")
    for c in candidates:
        if c.exists():
            load_dotenv(c, override=False)
            break


def _upsert_source(session, data: dict):
    name = data["name"]
    src = session.query(DaasSource).filter(DaasSource.name == name).first()
    created = src is None
    if src is None:
        src = DaasSource(name=name)
    src.label = data.get("label", name)
    src.description = data.get("description")
    src.url = data.get("url")
    src.config = data.get("config") or {}
    src.enabled = data.get("enabled", True)
    if data.get("score") is not None:
        src.score = data["score"]
    session.add(src)
    session.flush()
    return src, created


def _upsert_function(session, source_id: int, data: dict) -> bool:
    name = data["name"]
    fn = (
        session.query(DaasFunction)
        .filter(DaasFunction.source_id == source_id, DaasFunction.name == name)
        .first()
    )
    created = fn is None
    if fn is None:
        fn = DaasFunction(source_id=source_id, name=name)
    fn.label = data.get("label", "")
    fn.description = data.get("description", "")
    fn.category = data.get("category", "未分类")
    fn.parameters = data.get("parameters") or []
    fn.output_type = data.get("output_type", "DataFrame")
    fn.frequency = data.get("frequency")  # None = unset
    session.add(fn)
    session.flush()
    # Replace columns wholesale (matches registry_service upsert pattern).
    session.query(DaasFunctionColumn).filter(
        DaasFunctionColumn.function_id == fn.id
    ).delete()
    for col in data.get("columns", []) or []:
        session.add(
            DaasFunctionColumn(
                function_id=fn.id,
                name=col.get("name", ""),
                label=col.get("label"),
                type=col.get("type"),
                description=col.get("description"),
                nullable=col.get("nullable", True),
            )
        )
    return created


def _upsert_entity(session, data: dict):
    etype = data["entity_type"]
    code = data["code"]
    ent = (
        session.query(Entity)
        .filter(Entity.entity_type == etype, Entity.code == code)
        .first()
    )
    created = ent is None
    if ent is None:
        ent = Entity(entity_type=etype, code=code)
    ent.name = data["name"]
    ent.ticker = data.get("ticker")
    ent.exchange = data.get("exchange")
    ent.country_code = data.get("country_code")
    ent.isin = data.get("isin")
    ent.aliases = data.get("aliases") or []
    ent.status = data.get("status", "active")
    ent.metadata_ = data.get("metadata") or {}
    session.add(ent)
    session.flush()
    return ent, created


def _upsert_link(session, entity_id: int, source_id: int, identifier) -> bool:
    link = (
        session.query(EntityDatasourceLink)
        .filter(
            EntityDatasourceLink.entity_id == entity_id,
            EntityDatasourceLink.source_id == source_id,
        )
        .first()
    )
    created = link is None
    if link is None:
        link = EntityDatasourceLink(entity_id=entity_id, source_id=source_id)
    if identifier is not None:
        link.identifier_in_source = identifier
    link.coverage = "full"
    session.add(link)
    return created


def _upsert_indicator(session, data: dict) -> bool:
    name = data["name"]
    ir = session.query(IndicatorRule).filter(IndicatorRule.name == name).first()
    created = ir is None
    if ir is None:
        ir = IndicatorRule(name=name)
    ir.datasource = data["datasource"]
    ir.function_name = data["function_name"]
    ir.source_table = data["source_table"]
    ir.date_column = data["date_column"]
    ir.value_column = data["value_column"]
    ir.op = data["op"]
    ir.params_json = data.get("params_json") or {}
    ir.indicator_name = data["indicator_name"]
    if data.get("score") is not None:
        ir.score = data["score"]
    ir.enabled = data.get("enabled", True)
    session.add(ir)
    return created


def main() -> int:
    ap = argparse.ArgumentParser(description="Load a registry JSON into the daas DB.")
    ap.add_argument("json_file", help="Path to the registry JSON file.")
    ap.add_argument("--env", help="Path to a .env file (default: repo root .env).")
    ap.add_argument("--dry-run", action="store_true", help="Parse + print, do not write.")
    args = ap.parse_args()

    _load_env(args.env)
    db_url = os.environ.get("DAAS_DATABASE_URL", "(unset → default mcp/daas.db)")
    print(f"DB URL: {db_url}")

    with open(args.json_file, encoding="utf-8") as f:
        data = json.load(f)

    db = get_database()  # reads DAAS_DATABASE_URL, runs create_all + migrations
    session = db.get_session()

    counts = {"functions": 0, "entities": 0, "links": 0, "indicators": 0}
    try:
        src_data = data.get("source") or {}
        if not src_data.get("name"):
            print("ERROR: JSON missing 'source.name'")
            return 2
        src, src_created = _upsert_source(session, src_data)
        print(f"source '{src.name}': {'created' if src_created else 'exists'} (id={src.id})")

        funcs = data.get("functions", []) or []
        for fn_data in funcs:
            if _upsert_function(session, src.id, fn_data):
                counts["functions"] += 1
        print(f"functions: {len(funcs)} processed ({counts['functions']} new)")

        ents = data.get("entities", []) or []
        for ent_data in ents:
            ent, ent_created = _upsert_entity(session, ent_data)
            if ent_created:
                counts["entities"] += 1
            ident = ent_data.get("identifier_in_source")
            if _upsert_link(session, ent.id, src.id, ident):
                counts["links"] += 1
        print(
            f"entities: {len(ents)} processed "
            f"({counts['entities']} new, {counts['links']} new links)"
        )

        rules = data.get("indicator_rules", []) or []
        for ir_data in rules:
            if _upsert_indicator(session, ir_data):
                counts["indicators"] += 1
        print(f"indicator_rules: {len(rules)} processed ({counts['indicators']} new)")

        if args.dry_run:
            session.rollback()
            print("[DRY RUN] rolled back, no changes committed.")
        else:
            session.commit()
            print("committed.")
    except Exception as e:
        session.rollback()
        print(f"ERROR: {type(e).__name__}: {e}")
        return 1
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
