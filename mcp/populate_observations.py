"""
Populate observations table from DAAS source functions.

Usage:
  python3 populate_observations.py --source cnstats --all
  python3 populate_observations.py --source cnstats --function cnstats_gdp_quarterly
  python3 populate_observations.py --source worldbank --function worldbank_ny_gdp_mktp_cd
"""
import argparse
import os
import sys

_MCP_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_MCP_DIR)
_HARNESS = os.path.join(_PROJ, "daas-agent-harness")
sys.path.insert(0, _HARNESS)

from cli_anything.daas.core.models import Base, Observation, Function, Source
from cli_anything.daas.sources.router import SourceRouter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_engine():
    url = os.environ.get("DAAS_DATABASE_URL", f"sqlite:///{_MCP_DIR}/daas.db")
    return create_engine(url, echo=False)


def create_tables(engine):
    Base.metadata.create_all(engine)


def normalize_cnstats(df, function_name):
    """Pivot wide cnstats row into long observations."""
    import pandas

    date_col = None
    for candidate in ("日期", "月份"):
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col is None:
        print(f"  normalize_cnstats: no date col in {list(df.columns)}, skipping")
        return []

    is_type1 = "今值" in df.columns and "商品" in df.columns

    rows = []
    for _, row in df.iterrows():
        r = row.to_dict()
        date = str(r.pop(date_col))

        if is_type1:
            label = str(r.pop("商品", ""))
            value = r.pop("今值", None)
            if value is not None and not (isinstance(value, float) and pandas.isna(value)):
                meta = {"label": label}
                for k in ("预测值", "前值"):
                    v = r.pop(k, None)
                    if v is not None and not (isinstance(v, float) and pandas.isna(v)):
                        meta[k] = v
                rows.append({
                    "source": "cnstats",
                    "function_name": function_name,
                    "indicator": "今值",
                    "date": date,
                    "value": str(value),
                    "metadata": meta,
                })
        else:
            for col, val in r.items():
                if val is None or (isinstance(val, float) and pandas.isna(val)):
                    continue
                rows.append({
                    "source": "cnstats",
                    "function_name": function_name,
                    "indicator": col,
                    "date": date,
                    "value": str(val),
                    "metadata": {},
                })
    return rows


def normalize_worldbank(df, function_name):
    """Map worldbank rows directly to observations."""
    import pandas

    rows = []
    for _, row in df.iterrows():
        r = row.to_dict()
        country = r.pop("country", None)
        year = str(r.pop("year", ""))
        for col, val in r.items():
            if col == "year":
                continue
            if val is None or (isinstance(val, float) and pandas.isna(val)):
                continue
            rows.append({
                "source": "worldbank",
                "function_name": function_name,
                "indicator": col,
                "date": year,
                "value": str(val),
                "metadata": {"country": country},
            })
    return rows


def store_observations(session, rows):
    """Upsert: insert or replace on conflict."""
    count = 0
    for r in rows:
        existing = (
            session.query(Observation)
            .filter_by(
                source=r["source"],
                function_name=r["function_name"],
                indicator=r["indicator"],
                date=r["date"],
            )
            .first()
        )
        if existing:
            existing.value = r["value"]
            existing.metadata_ = r.get("metadata", {})
        else:
            session.add(Observation(**r))
        count += 1
        if count % 100 == 0:
            session.flush()
    session.commit()
    return count


def populate(source_name, function_name=None):
    engine = get_engine()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        router = SourceRouter()
        if function_name:
            func_names = [function_name]
        else:
            funcs = (
                session.query(Function)
                .join(Source)
                .filter(Source.name == source_name)
                .all()
            )
            func_names = [f.name for f in funcs]

        import pandas as pd

        total = 0
        for fname in func_names:
            print(f"Fetching {fname}...")
            try:
                result = router.route(fname)
            except Exception as e:
                print(f"  SKIP: {e}")
                continue
            df = result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)
            print(f"  {len(df)} rows returned")

            if source_name == "cnstats":
                rows = normalize_cnstats(df, fname)
            elif source_name == "worldbank":
                rows = normalize_worldbank(df, fname)
            else:
                print(f"  skipping: no normalizer for source '{source_name}'")
                continue

            stored = store_observations(session, rows)
            total += stored
            print(f"  {stored} observations upserted")

        print(f"\nDone. {total} total observations upserted for {source_name}")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate DAAS observations table")
    parser.add_argument("--source", required=True, choices=["cnstats", "worldbank", "ckan"])
    parser.add_argument("--function", default=None)
    parser.add_argument("--all", dest="all_funcs", action="store_true")
    args = parser.parse_args()

    if not args.function and not args.all_funcs:
        parser.error("specify --function or --all")

    populate(args.source, function_name=args.function)
