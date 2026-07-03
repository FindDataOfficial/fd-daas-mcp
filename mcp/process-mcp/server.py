"""
MCP Server for process-mcp — multi-model LLM extraction + math indicators.

LLM extraction (11):
  list_models        — configured models + which support vision
  list_source_tables — scraped source-data tables (scraw_<slug>) with row counts
  create_rule        — bind a source table + text column + schema + model
  list_rules         — all rules
  get_rule           — one rule by name
  update_rule        — update rule fields (only provided ones)
  delete_rule        — delete a rule (cascades to its results)
  run_rule           — incrementally extract from new source rows → process_results
  extract_text       — ad-hoc long-text extraction (chunked, no truncation)
  extract_image      — ad-hoc image extraction via a vision model
  extract_file       — read a local .txt/.md/.pdf and extract

Math indicators (8) — deterministic pandas, results → daas `observations`:
  list_indicator_ops — the fixed op catalog (sma, ema, rsi, pct_change, ...)
  create_indicator   — bind a datasource + source table + op to an indicator name
  list_indicators    — all indicator rules
  get_indicator      — one indicator rule by name
  update_indicator   — update indicator fields (only provided ones)
  delete_indicator   — delete an indicator rule (observations rows survive)
  run_indicator      — full-recompute the indicator → observations (idempotent)
  calculate          — ad-hoc compute over a source table without persisting

Cron: `python server.py --run-rule <name>` (LLM) or `--run-indicator <name>`
(indicator) runs the path in-process and exits.

Entry: python3 server.py  (FastMCP, stdio transport)
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Unified env: root .env first, then per-MCP .env with override=True
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

# make mcp/models importable
_MODELS = Path(__file__).resolve().parent.parent / "models"
if str(_MODELS) not in sys.path:
    sys.path.insert(0, str(_MODELS))

from fastmcp import FastMCP  # noqa: E402

import process_tools as T  # noqa: E402
import indicator_tools as IT  # noqa: E402
from process_database import ProcessError as DbError  # noqa: E402
from process_database import get_db  # noqa: E402
from process_tools import ProcessError as ToolError  # noqa: E402
from indicator_tools import IndicatorError as IndError  # noqa: E402

logger = logging.getLogger("process-mcp")
app = FastMCP(name="process-mcp")

_DEFAULT_BATCH = 500


# ── model + source discovery ────────────────────────────────────


@app.tool
def list_models() -> dict:
    """Return configured models with a `vision` flag each. API keys are never returned."""
    return T.list_models()


@app.tool
def list_source_tables() -> dict:
    """Return scraped source-data tables (name LIKE 'scraw_%') with row counts + columns."""
    return {"tables": get_db().list_source_tables()}


# ── rule CRUD ───────────────────────────────────────────────────


@app.tool
def create_rule(
    name: str,
    source_table: str,
    text_column: str,
    schema: dict,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_chars: int = 12000,
    datasource: Optional[str] = None,
    enabled: bool = True,
) -> dict:
    """Create a processing rule bound to a scraped source table.

    Args:
        name: unique rule name.
        source_table: scraped source-data table name (convention: scraw_<slug>).
        text_column: the column in source_table holding the text to extract from.
        schema: JSON Schema each extracted record must conform to.
        prompt: optional extra instructions.
        model: optional model name from list_models (default = first).
        max_chars: chunk size for long text (default 12000).
        datasource: optional daas sources.name for traceability.
        enabled: whether run_rule will process this rule.
    """
    try:
        return get_db().create_rule(
            name=name,
            source_table=source_table,
            text_column=text_column,
            schema_json=schema,
            prompt=prompt,
            model=model,
            max_chars=max_chars,
            datasource=datasource,
            enabled=enabled,
        )
    except DbError as e:
        return {"error": str(e)}


@app.tool
def list_rules() -> dict:
    """Return all processing rules."""
    return {"rules": get_db().list_rules()}


@app.tool
def get_rule(name: str) -> dict:
    """Return one rule by name."""
    row = get_db().get_rule(name)
    return row if row is not None else {"error": f"rule not found: {name}"}


@app.tool
def update_rule(
    name: str,
    source_table: Optional[str] = None,
    text_column: Optional[str] = None,
    schema: Optional[dict] = None,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_chars: Optional[int] = None,
    datasource: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> dict:
    """Update a rule's fields. Only provided fields change. The rule name cannot be renamed."""
    fields = {
        "source_table": source_table,
        "text_column": text_column,
        "schema_json": schema,
        "prompt": prompt,
        "model": model,
        "max_chars": max_chars,
        "datasource": datasource,
        "enabled": enabled,
    }
    # drop None fields (allow None-clearable ones by passing explicit values where needed)
    fields = {k: v for k, v in fields.items() if v is not None}
    try:
        return get_db().update_rule(name, **fields)
    except DbError as e:
        return {"error": str(e)}


@app.tool
def delete_rule(name: str) -> dict:
    """Delete a rule. Its process_results rows are removed via FK CASCADE."""
    ok = get_db().delete_rule(name)
    return {"deleted": name, "results_cascaded": True} if ok else {"error": f"rule not found: {name}"}


# ── run_rule (incremental, idempotent) ──────────────────────────


def _run_rule_impl(name: str, batch: int = _DEFAULT_BATCH) -> dict:
    """Incremental extraction: new source rows → process_results, advance cursor."""
    db = get_db()
    rule = db.get_rule_row(name)
    if rule is None:
        return {"error": f"rule not found: {name}"}
    if not rule.enabled:
        return {"error": f"rule disabled: {name}"}

    schema = rule.schema_json or {}
    rows = db.fetch_source_rows(rule.source_table, rule.text_column, rule.last_rowid, batch)
    if not rows:
        return {
            "rule": name,
            "processed": 0,
            "failed": 0,
            "next_rowid": rule.last_rowid,
            "up_to_date": True,
        }

    processed = 0
    failed = 0
    max_rowid = rule.last_rowid
    for rowid, text in rows:
        max_rowid = max(max_rowid, rowid)
        result = T.extract_text(
            text,
            schema,
            prompt=rule.prompt,
            model=rule.model,
            max_chars=rule.max_chars,
        )
        if "records" in result:
            db.upsert_result(
                rule.id,
                rule.source_table,
                rowid,
                {"records": result["records"], "count": result.get("count", 0)},
                rule.model,
            )
            processed += 1
        else:
            db.upsert_result(
                rule.id, rule.source_table, rowid, {"error": result.get("error", "unknown"), "detail": result.get("detail")}, rule.model
            )
            failed += 1

    db.advance_cursor(rule.id, max_rowid)
    return {
        "rule": name,
        "processed": processed,
        "failed": failed,
        "next_rowid": max_rowid,
        "up_to_date": len(rows) < batch,
    }


@app.tool
def run_rule(name: str, batch: int = _DEFAULT_BATCH) -> dict:
    """Incrementally extract from a rule's source table into process_results.

    Reads rows with rowid > rule.last_rowid (limited to `batch`), extracts each
    against the rule's schema, upserts results, and advances the cursor.
    Safe to re-run: existing results are upserted, never duplicated.
    """
    try:
        return _run_rule_impl(name, batch=batch)
    except (DbError, ToolError) as e:
        return {"error": str(e)}


# ── ad-hoc extraction tools ─────────────────────────────────────


@app.tool
def extract_text(
    text: str,
    schema: dict,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_chars: int = 12000,
) -> dict:
    """Extract structured records from (possibly long) text.

    Long text is chunked (no truncation): per-chunk extraction then a merge pass.
    """
    return T.extract_text(text, schema, prompt=prompt, model=model, max_chars=max_chars)


@app.tool
def extract_image(
    image: str,
    schema: dict,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Extract structured records from an image via a vision-capable model.

    `image` accepts a local file path, an http(s):// URL, or raw base64.
    """
    return T.extract_image(image, schema, prompt=prompt, model=model)


@app.tool
def extract_file(
    path: str,
    schema: dict,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_chars: int = 12000,
) -> dict:
    """Read a local .txt/.md/.pdf and extract structured records."""
    return T.extract_file(path, schema, prompt=prompt, model=model, max_chars=max_chars)


# ── indicator tools (deterministic math → observations) ────────


@app.tool
def list_indicator_ops() -> dict:
    """Return the fixed math-op catalog with each op's required params."""
    return IT.list_indicator_ops()


@app.tool
def create_indicator(
    name: str,
    datasource: str,
    source_table: str,
    date_column: str,
    value_column: str,
    op: str,
    params: Optional[dict] = None,
    function_name: Optional[str] = None,
    indicator_name: Optional[str] = None,
    enabled: bool = True,
) -> dict:
    """Create an indicator rule bound to a datasource + source table.

    Args:
        name: unique indicator-rule name.
        datasource: daas `sources.name` (validated; soft reference).
        source_table: any table in daas.db holding the series.
        date_column: the column to order by (and key observations on).
        value_column: the numeric column the op is computed over.
        op: one of list_indicator_ops (e.g. 'sma', 'pct_change', 'rsi').
        params: op params, e.g. {"window": 5} for sma/rsi/zscore.
        function_name: label written to observations.function_name (defaults to source_table).
        indicator_name: output indicator label (defaults to the rule name).
        enabled: whether run_indicator will process this rule.
    """
    try:
        return get_db().create_indicator(
            name=name,
            datasource=datasource,
            source_table=source_table,
            date_column=date_column,
            value_column=value_column,
            op=op,
            params=params,
            function_name=function_name,
            indicator_name=indicator_name,
            enabled=enabled,
        )
    except (DbError, IndError) as e:
        return {"error": str(e)}


@app.tool
def list_indicators() -> dict:
    """Return all indicator rules."""
    return {"indicators": get_db().list_indicators()}


@app.tool
def get_indicator(name: str) -> dict:
    """Return one indicator rule by name."""
    row = get_db().get_indicator(name)
    return row if row is not None else {"error": f"indicator not found: {name}"}


@app.tool
def update_indicator(
    name: str,
    datasource: Optional[str] = None,
    source_table: Optional[str] = None,
    date_column: Optional[str] = None,
    value_column: Optional[str] = None,
    op: Optional[str] = None,
    params: Optional[dict] = None,
    function_name: Optional[str] = None,
    indicator_name: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> dict:
    """Update an indicator rule's fields. Only provided fields change. The
    rule name cannot be renamed. Pass `params` to replace the op params."""
    fields = {
        "datasource": datasource,
        "source_table": source_table,
        "date_column": date_column,
        "value_column": value_column,
        "op": op,
        "params_json": params,
        "function_name": function_name,
        "indicator_name": indicator_name,
        "enabled": enabled,
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    try:
        return get_db().update_indicator(name, **fields)
    except (DbError, IndError) as e:
        return {"error": str(e)}


@app.tool
def delete_indicator(name: str) -> dict:
    """Delete an indicator rule. observations rows it produced are NOT removed
    (soft reference) — they remain identifiable via their `metadata.rule_name`."""
    ok = get_db().delete_indicator(name)
    return {"deleted": name} if ok else {"error": f"indicator not found: {name}"}


@app.tool
def run_indicator(name: str) -> dict:
    """Full-recompute the indicator over its source table → observations.

    Reads the whole source table, computes the op, and upserts every
    (date, value) into the daas `observations` table keyed on
    (source=datasource, function_name, indicator=indicator_name, date).
    Idempotent on re-run via the observations unique constraint.
    """
    try:
        return get_db().run_indicator(name)
    except (DbError, IndError) as e:
        return {"error": str(e)}


@app.tool
def calculate(
    source_table: str,
    date_column: str,
    value_column: str,
    op: str,
    params: Optional[dict] = None,
    datasource: Optional[str] = None,
    function_name: Optional[str] = None,
    indicator_name: Optional[str] = None,
) -> dict:
    """Ad-hoc: compute an indicator over a source table without persisting.

    Validates table/columns/op/params, reads the series, computes, and returns
    {indicator, dates, values, count}. Writes nothing (no rule, no observations).
    """
    return IT.calculate(
        get_db(),
        source_table,
        date_column,
        value_column,
        op,
        params=params,
        datasource=datasource,
        function_name=function_name,
        indicator_name=indicator_name,
    )


# ── CLI branch (cron-driven) + entry ────────────────────────────


def _cli_run_rule(name: str) -> int:
    """Run a rule in-process, print JSON summary, return exit code."""
    try:
        summary = _run_rule_impl(name)
    except (DbError, ToolError) as e:
        summary = {"error": str(e)}
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0 if "error" not in summary else 1


def _cli_run_indicator(name: str) -> int:
    """Run an indicator in-process, print JSON summary, return exit code."""
    try:
        summary = get_db().run_indicator(name)
    except (DbError, IndError) as e:
        summary = {"error": str(e)}
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0 if "error" not in summary else 1


if __name__ == "__main__":
    if "--run-rule" in sys.argv:
        i = sys.argv.index("--run-rule")
        if i + 1 >= len(sys.argv):
            print(json.dumps({"error": "--run-rule requires a rule name"}))
            sys.exit(2)
        sys.exit(_cli_run_rule(sys.argv[i + 1]))
    if "--run-indicator" in sys.argv:
        i = sys.argv.index("--run-indicator")
        if i + 1 >= len(sys.argv):
            print(json.dumps({"error": "--run-indicator requires an indicator name"}))
            sys.exit(2)
        sys.exit(_cli_run_indicator(sys.argv[i + 1]))
    app.run(transport="stdio", show_banner=False)
