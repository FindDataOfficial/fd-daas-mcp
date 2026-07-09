"""
Datasource seed template — register a purpose-built MCP as a daas datasource.

Mirrors mcp/daas-mcp/seed_external_mcps.py. Run from within mcp/daas-mcp/:

    uv run --directory mcp/daas-mcp python ../../.claude/skills/fd-datasource-mcp-creator/references/datasource-seed-template.py

Adapt for {{SOURCE}}. The pattern:

  1. create_category (under an appropriate parent — Filings/Market-Data/Macro)
  2. create_datasource (→ sources row)
  3. register daas_functions + daas_function_columns (the "logical functions"
     even when the live API is object-shaped — the matcher reads these)
  4. add_form + add_section with the routing grammar (one section per function)

The routing grammar is the single source of truth for how an agent dispatches
to the source. Validate it; never hand-write free-text instructions.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parent.parent.parent.parent.parent  # skill → .claude/skills/.. → repo root
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

# Run from within mcp/daas-mcp/ so `import models` + `import daas_database` work.
sys.path.insert(0, str(_REPO_ROOT / "mcp" / "daas-mcp"))

from sqlalchemy import delete, select  # noqa: E402
from daas_database import Database  # noqa: E402
from models import (  # noqa: E402
    Category,
    DaasFunction,
    DaasFunctionColumn,
    DaasSource,
    DatasourceForm,
    DatasourceSection,
)

# ════════════════════════════════════════════════════════════════════════
# Routing grammar — mcp=<mcp> tool=<tool> [param=k=v]*
# ════════════════════════════════════════════════════════════════════════
_ROUTING_RE = re.compile(r"^mcp=\S+\s+tool=\S+(\s+param=[^=\s]+=\S+)*$")


def validate_routing(instruction: str) -> None:
    if not _ROUTING_RE.match(instruction):
        raise ValueError(f"Malformed routing instruction: {instruction!r}")


# ════════════════════════════════════════════════════════════════════════
# Seed data — adapt these for your source
# ════════════════════════════════════════════════════════════════════════
SOURCE_NAME = "{{SOURCE}}"                       # 'weather', 'fred', ...
SOURCE_LABEL = "{{SOURCE_LABEL}}"
SOURCE_DESC = "{{SOURCE_DESCRIPTION}}"
SOURCE_URL = "{{SOURCE_URL}}"
SOURCE_CATEGORY = "{{CHILD_CATEGORY}}"            # leaf under a parent root
SOURCE_PARENT_CATEGORY = "{{PARENT_CATEGORY}}"   # 'Market-Data' / 'Macro' / 'Filings' / new root

# (function_name, label, category, routing_instruction, columns[])
# Each routing_instruction uses <ask-agent> for params the agent must supply.
FUNCTIONS: list[dict] = [
    {
        "name": "{{func_1}}",
        "label": "{{Func 1 label}}",
        "category": SOURCE_CATEGORY,
        "routing": f"mcp={SOURCE_NAME}-mcp tool=get_company param={{identifier}}=<ask-agent>",
        "columns": [
            {"name": "name", "label": "Name", "type": "TEXT"},
            {"name": "code", "label": "Code", "type": "TEXT"},
            # ... real columns from your Step-1 analysis
        ],
    },
]


def _resolve_category(session, name: str, label: str, parent_name: str | None) -> Category:
    cat = session.execute(select(Category).where(Category.name == name)).scalar_one_or_none()
    if cat:
        return cat
    parent = None
    if parent_name:
        parent = _resolve_category(session, parent_name, parent_name, None)
    cat = Category(name=name, label=label, parent_id=parent.id if parent else None)
    session.add(cat)
    session.flush()
    return cat


def _upsert_source(session) -> DaasSource:
    src = session.execute(select(DaasSource).where(DaasSource.name == SOURCE_NAME)).scalar_one_or_none()
    if src is None:
        src = DaasSource(name=SOURCE_NAME, label=SOURCE_LABEL,
                         description=SOURCE_DESC, url=SOURCE_URL, enabled=True)
        session.add(src)
    else:
        src.label = SOURCE_LABEL
        src.description = SOURCE_DESC
    session.flush()
    return src


def _upsert_function(session, src: DaasSource, spec: dict) -> DaasFunction:
    validate_routing(spec["routing"])
    fn = session.execute(select(DaasFunction).where(
        DaasFunction.source_id == src.id, DaasFunction.name == spec["name"]
    )).scalar_one_or_none()
    if fn is None:
        fn = DaasFunction(source_id=src.id, name=spec["name"], label=spec.get("label"),
                          category=spec.get("category", "未分类"), output_type="DataFrame")
        session.add(fn)
    else:
        fn.label = spec.get("label")
    session.flush()

    # Replace columns (idempotent re-seed) — SQLAlchemy 2.x delete idiom
    session.execute(delete(DaasFunctionColumn).where(DaasFunctionColumn.function_id == fn.id))
    for c in spec.get("columns", []):
        session.add(DaasFunctionColumn(function_id=fn.id, name=c["name"],
                                       label=c.get("label"), type=c.get("type"),
                                       description=c.get("description")))
    session.flush()
    return fn


def _upsert_form_and_sections(session, src: DaasSource, specs: list[dict]) -> None:
    form_name = f"{SOURCE_NAME}-default"
    # NOTE: datasource_forms uses `form_type` (not `name`); datasource_sections
    # uses `section_name` and has no `label` column. Match the real models.
    form = session.execute(select(DatasourceForm).where(DatasourceForm.form_type == form_name)).scalar_one_or_none()
    if form is None:
        form = DatasourceForm(form_type=form_name, source_id=src.id, label=f"{SOURCE_LABEL} default form")
        session.add(form)
    session.flush()
    for i, spec in enumerate(specs):
        sec_name = spec["name"]
        sec = session.execute(select(DatasourceSection).where(
            DatasourceSection.form_id == form.id, DatasourceSection.section_name == sec_name
        )).scalar_one_or_none()
        if sec is None:
            sec = DatasourceSection(form_id=form.id, section_name=sec_name,
                                    instruction=spec["routing"], sort_order=i)
            session.add(sec)
        else:
            sec.instruction = spec["routing"]
    session.flush()


def run(dry_run: bool = False) -> None:
    db = Database()
    session = db.get_session()
    try:
        _resolve_category(session, SOURCE_PARENT_CATEGORY, SOURCE_PARENT_CATEGORY, None)
        _resolve_category(session, SOURCE_CATEGORY, SOURCE_CATEGORY, SOURCE_PARENT_CATEGORY)
        src = _upsert_source(session)
        for spec in FUNCTIONS:
            _upsert_function(session, src, spec)
        _upsert_form_and_sections(session, src, FUNCTIONS)
        if dry_run:
            session.rollback()
            print("DRY RUN — no changes committed.")
        else:
            session.commit()
            print(f"Seeded source={SOURCE_NAME}: {len(FUNCTIONS)} functions, "
                  f"{sum(len(s['columns']) for s in FUNCTIONS)} columns.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run(dry_run=args.dry_run)
