"""Hermetic self-check for seed_massive_endpoints.py.

Temp DB (no network, no LLM, no Massive.com calls). Pre-creates the `massive`
source + its `default` form + 3 composable-tool sections (the minimal state
seed_external_mcps.py would leave behind), then runs the seeder and asserts:

  - ≥37 daas_functions under the massive source, each with ≥1 column.
  - The 5 representative endpoints carry the verified column sets.
  - 12 gated endpoints carry parameters.gated=true.
  - ≥25 indicator_rules with datasource=massive and source_table LIKE scraw_massive_%.
  - A second seed run is a no-op (idempotency).
  - --unseed removes only the owned functions+columns+indicators and leaves
    the massive source / default form / 3 sections intact.

Run:
    uv run --directory mcp/daas-mcp python selfcheck_massive_endpoints.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parent.parent.parent
sys.path.insert(0, str(_THIS.parent))

from sqlalchemy import inspect as sa_inspect  # noqa: E402

from daas_database import Database  # noqa: E402
from fd_daas_mcp.models import (  # noqa: E402
    DaasFunction,
    DaasFunctionColumn,
    DaasSource,
    DatasourceForm,
    DatasourceSection,
    IndicatorRule,
)
import seed_massive_endpoints as sms  # noqa: E402


FAILED = []


def check(cond, msg):
    status = "ok" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        FAILED.append(msg)


def _precreate_massive_source(session):
    """Minimal state seed_external_mcps.py owns: massive source + default form
    + 3 composable-tool sections. The self-check must leave these intact."""
    src = DaasSource(name="massive", label="Massive.com",
                     description="Massive.com (test)", url="https://massive.com",
                     enabled=True)
    session.add(src)
    session.commit()
    form = DatasourceForm(source_id=src.id, form_type="default",
                          label="Massive.com composable API")
    session.add(form)
    session.commit()
    for sec_name in ("Search-Endpoints", "Call-API", "Query-Data"):
        session.add(DatasourceSection(form_id=form.id, section_name=sec_name,
                                      instruction=f"mcp=massive-mcp tool=dummy param=q=<ask-agent>"))
    session.commit()
    return src.id


def main() -> int:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    tmp_path = tmp.name
    os.environ["DAAS_DATABASE_URL"] = f"sqlite:///{tmp_path}"
    Database._instance = None
    db = Database()
    session = db.get_session()

    try:
        massive_id = _precreate_massive_source(session)

        print("== Run 1: seed endpoints + indicators ==")
        counts1 = sms.Counts()
        sms.seed(session, counts1, dry_run=False, seed_indicators=True)
        print(f"  functions +{counts1.functions_new}, columns +{counts1.columns_new}, "
              f"indicators +{counts1.indicators_new}")

        # ── Function + column assertions ──
        fns = (session.query(DaasFunction)
               .filter(DaasFunction.source_id == massive_id).all())
        check(len(fns) >= 37, f"≥37 daas_functions under massive (got {len(fns)})")

        fn_by_name = {f.name: f for f in fns}
        for name, expected_cols in [
            ("reference_all_tickers",
             ["ticker", "name", "market", "locale", "primary_exchange", "type",
              "active", "currency_name", "cik", "composite_figi", "share_class_figi",
              "last_updated_utc"]),
            ("stocks_previous_bar", ["T", "v", "vw", "o", "c", "h", "l", "t_2", "n"]),
            ("options_chain_snapshot",
             ["details_contract_type", "details_expiration_date", "details_strike_price",
              "details_ticker", "open_interest", "underlying_asset_ticker",
              "day_close", "day_volume", "day_vwap"]),
            ("economy_treasury_yields",
             ["date", "yield_1_year", "yield_5_year", "yield_10_year"]),
            ("futures_products",
             ["asset_sub_class", "date", "product_code", "trade_currency_code",
              "trading_venue", "type", "unit_of_measure"]),
        ]:
            check(name in fn_by_name, f"function {name} exists")
            if name in fn_by_name:
                cols = {c.name for c in session.query(DaasFunctionColumn).filter(
                    DaasFunctionColumn.function_id == fn_by_name[name].id).all()}
                missing = [c for c in expected_cols if c not in cols]
                check(not missing, f"{name} has columns {expected_cols} (missing: {missing})")

        # every function has ≥1 column
        no_col = [f.name for f in fns if not session.query(DaasFunctionColumn).filter(
            DaasFunctionColumn.function_id == f.id).first()]
        check(not no_col, f"every function has ≥1 column (no-column: {no_col})")

        # parameters.path non-empty for all
        bad_path = [f.name for f in fns if not (f.parameters or {}).get("path")]
        check(not bad_path, f"every function parameters.path non-empty (bad: {bad_path})")

        # ── Gated assertions (12 gated) ──
        gated = [f.name for f in fns if (f.parameters or {}).get("gated") is True]
        check(len(gated) >= 12, f"≥12 gated endpoints (got {len(gated)}: {gated})")
        for must_gated in ("crypto_last_trade", "forex_last_quote", "indices_snapshot",
                           "options_last_trade", "alt_merchant_aggregates"):
            check(must_gated in gated, f"{must_gated} is gated")

        # ── Indicator assertions ──
        inds = (session.query(IndicatorRule)
                .filter(IndicatorRule.datasource == "massive").all())
        check(len(inds) >= 25, f"≥25 indicator_rules with datasource=massive (got {len(inds)})")
        bad_tbl = [i.name for i in inds if not i.source_table.startswith("scraw_massive_")]
        check(not bad_tbl, f"all indicator source_tables start with scraw_massive_ (bad: {bad_tbl})")
        bad_op = [i.name for i in inds if i.op not in
                  ("sma", "ema", "pct_change", "zscore", "rolling_std", "level")]
        check(not bad_op, f"all indicator ops in catalog (bad: {bad_op})")
        # windowed ops have their param
        bad_param = []
        for i in inds:
            if i.op in ("sma", "zscore", "rolling_std") and "window" not in (i.params_json or {}):
                bad_param.append(i.name)
            if i.op == "ema" and "span" not in (i.params_json or {}):
                bad_param.append(i.name)
        check(not bad_param, f"windowed ops have required params (bad: {bad_param})")

        # ── Run 2: idempotency (no new rows) ──
        print("== Run 2: idempotency ==")
        counts2 = sms.Counts()
        sms.seed(session, counts2, dry_run=False, seed_indicators=True)
        check(counts2.functions_new == 0 and counts2.indicators_new == 0,
              f"second run creates nothing (fn +{counts2.functions_new}, ind +{counts2.indicators_new})")

        # ── --unseed: removes owned rows, leaves massive source/form/sections ──
        print("== Run 3: --unseed ==")
        counts3 = sms.Counts()
        sms.unseed(session, counts3)
        print(f"  -{counts3.deleted['functions']} functions, -{counts3.deleted['columns']} columns, "
              f"-{counts3.deleted['indicators']} indicators")

        fns_after = (session.query(DaasFunction)
                     .filter(DaasFunction.source_id == massive_id).all())
        check(not fns_after, f"no daas_functions remain under massive (got {len(fns_after)})")
        inds_after = (session.query(IndicatorRule)
                      .filter(IndicatorRule.datasource == "massive").all())
        check(not inds_after, f"no indicator_rules remain for massive (got {len(inds_after)})")

        # massive source + default form + 3 sections survive
        src_after = session.query(DaasSource).filter(DaasSource.name == "massive").first()
        check(src_after is not None, "massive source survives --unseed")
        forms_after = (session.query(DatasourceForm)
                       .filter(DatasourceForm.source_id == massive_id).all())
        check(len(forms_after) == 1 and forms_after[0].form_type == "default",
              "massive default form survives --unseed")
        secs_after = (session.query(DatasourceSection)
                      .filter(DatasourceSection.form_id == forms_after[0].id).all())
        check(len(secs_after) == 3, f"3 massive sections survive --unseed (got {len(secs_after)})")

    finally:
        session.close()
        Database._instance = None
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if FAILED:
        print(f"\nFAILED {len(FAILED)} checks:")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print("\nAll self-checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
