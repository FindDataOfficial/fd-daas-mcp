"""Entity sync — populate `entities` (stocks + countries) in daas.db and
derive `entity_datasource_links` to the existing daas datasources.

Stocks come from akshare's market-list functions (A-shares, HK, US).
Countries come from a curated static list (~30 important markets). For
each entity, datasource links are auto-derived by market/country rules
(e.g. US stock → edgar + yfinance; A-share → cnreport + yfinance; HK →
hkex + yfinance; country → worldbank, + cnstats for CN). Manual links are
never deleted by the sync.

Runs in the daas-mcp venv. akshare is imported lazily so the daas-mcp
server (which doesn't need it) still starts if akshare is absent; pass
`--sync-stocks`/`--sync-all` and the script will print a clear error if
akshare isn't installed. The canonical way to run with akshare is:

    uv run --with akshare --directory mcp/daas-mcp python entity_sync.py --sync-all

Idempotent: re-runnable on the live daas.db. Upserts on (entity_type, code).
Stale stock codes (present before, absent now) are marked status='delisted'
(rows retained for link history).

Usage:
    entity_sync.py --sync-all              # stocks + countries + links
    entity_sync.py --sync-stocks           # stocks only
    entity_sync.py --sync-countries        # countries only
    entity_sync.py --register-cron         # install weekly refresh task+schedule
    entity_sync.py --sync-all --dry-run    # plan only, no writes
    entity_sync.py --db-url sqlite:///x.db # override DAAS_DATABASE_URL
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parent.parent.parent  # mcp/daas-mcp/ → mcp/ → repo root
try:
    load_dotenv(_REPO_ROOT / ".env")
    load_dotenv(_THIS.parent / ".env", override=True)
except ImportError:
    pass

sys.path.insert(0, str(_THIS.parent))

from sqlalchemy.orm import Session  # noqa: E402

from daas_database import Database  # noqa: E402
from models import (  # noqa: E402
    Entity,
    EntityDatasourceLink,
    DaasSource,
    Schedule,
    Task,
)


# ════════════════════════════════════════════════════════════════════════
# Curated country list — ISO 3166-1 alpha-2 + name (~30 important markets)
# ════════════════════════════════════════════════════════════════════════
COUNTRIES: list[tuple[str, str]] = [
    ("CN", "China"), ("US", "United States"), ("JP", "Japan"), ("HK", "Hong Kong"),
    ("GB", "United Kingdom"), ("DE", "Germany"), ("FR", "France"), ("KR", "South Korea"),
    ("SG", "Singapore"), ("TW", "Taiwan"), ("IN", "India"), ("AU", "Australia"),
    ("CA", "Canada"), ("BR", "Brazil"), ("RU", "Russia"), ("IT", "Italy"),
    ("ES", "Spain"), ("NL", "Netherlands"), ("CH", "Switzerland"), ("SE", "Sweden"),
    ("MX", "Mexico"), ("ID", "Indonesia"), ("TH", "Thailand"), ("MY", "Malaysia"),
    ("PH", "Philippines"), ("VN", "Vietnam"), ("SA", "Saudi Arabia"), ("AE", "United Arab Emirates"),
    ("ZA", "South Africa"), ("TR", "Turkey"),
]


# ════════════════════════════════════════════════════════════════════════
# Market configs — akshare list functions + column mapping + link rules
# ════════════════════════════════════════════════════════════════════════

def _a_share_exchange(code: str) -> Optional[str]:
    """Infer SSE / SZSE / BSE from an A-share code prefix."""
    if not code:
        return None
    c0 = code[0]
    if c0 == "6":          # 60xxxx main board, 688xxx STAR → Shanghai
        return "SSE"
    if c0 in ("0", "3"):   # 00xxxx main, 30xxxx ChiNext → Shenzhen
        return "SZSE"
    if c0 in ("8", "4"):   # 8xxxxx / 4xxxxx → Beijing
        return "BSE"
    return None


def _yf_a_share(code: str) -> str:
    ex = _a_share_exchange(code)
    suffix = {"SSE": "SS", "SZSE": "SZ", "BSE": "BJ"}.get(ex, "SS")
    return f"{code}.{suffix}"


def _yf_hk(code: str) -> str:
    # akshare gives 5-digit ('00700'); yfinance wants 4-digit ('0700.HK')
    return f"{code.lstrip('0').zfill(4)}.HK"


def _clean_code(val) -> str:
    """Strip whitespace; collapse float-int ('600519.0' → '600519')."""
    s = str(val).strip()
    if s.endswith(".0"):
        try:
            s = str(int(float(s)))
        except ValueError:
            pass
    return s


def _first_col(cols: list[str], candidates: list[str]) -> Optional[str]:
    for c in candidates:
        if c in cols:
            return c
    return None


def derive_links(
    entity_type: str,
    code: str,
    ticker: Optional[str] = None,
    market: Optional[str] = None,
) -> list[tuple[str, str]]:
    """Rule table: (entity) → list of (source_name, identifier_in_source).

    Only sources that exist in `sources` will actually get a link row — the
    caller filters by source_ids. Rules never delete; they only upsert."""
    if entity_type == "stock":
        if market == "CN-A":
            return [("cnreport", code), ("yfinance", _yf_a_share(code))]
        if market == "HK":
            return [("hkex", code), ("yfinance", _yf_hk(code))]
        if market == "US":
            t = ticker or code
            return [("edgar", t), ("yfinance", t)]
        if market == "JP":
            return [("edinet", ticker or code)]
        return []
    if entity_type == "country":
        links = [("worldbank", code)]
        if code == "CN":
            links.append(("cnstats", "CN"))
        return links
    return []


MARKETS: list[dict] = [
    {
        "market": "CN-A",
        "func": "stock_info_a_code_name",
        "code_cols": ["code", "代码", "symbol"],
        "name_cols": ["name", "名称"],
        "country_code": "CN",
        "exchange_fn": _a_share_exchange,
    },
    {
        "market": "HK",
        "func": "stock_hk_spot_em",
        "code_cols": ["代码", "code", "symbol"],
        "name_cols": ["名称", "name"],
        "country_code": "HK",
        "exchange": "HKEX",
        "zfill": 5,
    },
    {
        "market": "US",
        "func": "stock_us_spot_em",
        "code_cols": ["代码", "code", "symbol"],
        "name_cols": ["名称", "name"],
        "country_code": "US",
        "exchange": "US",
    },
]


# ════════════════════════════════════════════════════════════════════════
# Counters
# ════════════════════════════════════════════════════════════════════════
class Counts:
    def __init__(self) -> None:
        self.entities_new = 0
        self.entities_updated = 0
        self.entities_unchanged = 0
        self.entities_delisted = 0
        self.links_new = 0
        self.links_updated = 0
        self.links_unchanged = 0
        self.links_skipped_missing_source = 0
        self.market_errors = 0

    def print_summary(self) -> None:
        print(f"  entities   +{self.entities_new} (~{self.entities_updated} updated, "
              f"{self.entities_unchanged} unchanged, {self.entities_delisted} delisted)")
        print(f"  links      +{self.links_new} (~{self.links_updated} updated, "
              f"{self.links_unchanged} unchanged, {self.links_skipped_missing_source} skipped-no-source)")
        if self.market_errors:
            print(f"  market errors: {self.market_errors}")


# ════════════════════════════════════════════════════════════════════════
# Upsert helpers
# ════════════════════════════════════════════════════════════════════════

def upsert_entity(
    session: Session,
    entity_type: str,
    code: str,
    name: str,
    ticker: Optional[str] = None,
    exchange: Optional[str] = None,
    country_code: Optional[str] = None,
    isin: Optional[str] = None,
    aliases: Optional[list] = None,
    status: str = "active",
    dry_run: bool = False,
    counts: Optional[Counts] = None,
) -> Optional[Entity]:
    existing = (
        session.query(Entity)
        .filter(Entity.entity_type == entity_type, Entity.code == code)
        .first()
    )
    if existing is not None:
        changed = False
        if name and existing.name != name:
            existing.name = name
            changed = True
        if ticker and existing.ticker != ticker:
            existing.ticker = ticker
            changed = True
        if exchange and existing.exchange != exchange:
            existing.exchange = exchange
            changed = True
        if country_code and existing.country_code != country_code:
            existing.country_code = country_code
            changed = True
        # Sync re-confirms the entity is still listed → flip delisted→active
        if existing.status != "active" and status == "active":
            existing.status = "active"
            changed = True
        if counts:
            counts.entities_updated += 1 if changed else 0
            counts.entities_unchanged += 0 if changed else 1
        if changed and not dry_run:
            session.commit()
        return existing
    if counts:
        counts.entities_new += 1
    if dry_run:
        return None
    e = Entity(
        entity_type=entity_type,
        code=code,
        name=name,
        ticker=ticker,
        exchange=exchange,
        country_code=country_code,
        isin=isin,
        aliases=aliases,
        status=status,
    )
    session.add(e)
    session.commit()
    return e


def upsert_links(
    session: Session,
    entity: Optional[Entity],
    entity_type: str,
    code: str,
    ticker: Optional[str],
    market: Optional[str],
    source_ids: dict[str, int],
    dry_run: bool,
    counts: Counts,
) -> None:
    """Derive + upsert links for one entity. Never deletes manual links."""
    rules = derive_links(entity_type, code, ticker=ticker, market=market)
    for source_name, identifier in rules:
        if source_name not in source_ids:
            counts.links_skipped_missing_source += 1
            continue
        if entity is None:  # dry-run: count planned, no writes
            counts.links_new += 1
            continue
        sid = source_ids[source_name]
        existing = (
            session.query(EntityDatasourceLink)
            .filter(
                EntityDatasourceLink.entity_id == entity.id,
                EntityDatasourceLink.source_id == sid,
            )
            .first()
        )
        if existing is not None:
            if existing.identifier_in_source != identifier:
                if not dry_run:
                    existing.identifier_in_source = identifier
                    session.commit()
                counts.links_updated += 1
            else:
                counts.links_unchanged += 1
        else:
            if not dry_run:
                session.add(
                    EntityDatasourceLink(
                        entity_id=entity.id,
                        source_id=sid,
                        identifier_in_source=identifier,
                        coverage="full",
                    )
                )
                session.commit()
            counts.links_new += 1


def mark_delisted(
    session: Session,
    market: str,
    seen_codes: set[str],
    dry_run: bool,
    counts: Counts,
) -> None:
    """Set status='delisted' on active stock entities of this market whose
    code is absent from the current list. Rows are retained (link history)."""
    q = session.query(Entity).filter(
        Entity.entity_type == "stock", Entity.status == "active"
    )
    if market == "CN-A":
        q = q.filter(Entity.country_code == "CN", Entity.exchange.in_(["SSE", "SZSE", "BSE"]))
    elif market == "HK":
        q = q.filter(Entity.exchange == "HKEX")
    elif market == "US":
        q = q.filter(Entity.country_code == "US")
    else:
        return
    flagged = 0
    for e in q.all():
        if e.code not in seen_codes:
            flagged += 1
            if not dry_run:
                e.status = "delisted"
    if flagged and not dry_run:
        session.commit()
    counts.entities_delisted += flagged


# ════════════════════════════════════════════════════════════════════════
# Sync passes
# ════════════════════════════════════════════════════════════════════════

def sync_countries(session: Session, source_ids: dict[str, int], dry_run: bool, counts: Counts) -> None:
    print("Syncing countries...")
    for code, name in COUNTRIES:
        e = upsert_entity(
            session, "country", code, name,
            country_code=code, dry_run=dry_run, counts=counts,
        )
        upsert_links(session, e, "country", code, None, None, source_ids, dry_run, counts)
    print(f"  {len(COUNTRIES)} countries processed")


def sync_stocks(session: Session, source_ids: dict[str, int], dry_run: bool, counts: Counts) -> bool:
    print("Syncing stocks from akshare...")
    try:
        import akshare as ak
    except ImportError:
        print(
            "ERROR: akshare is not installed in this environment.\n"
            "       Re-run with:  uv run --with akshare --directory mcp/daas-mcp "
            "python entity_sync.py --sync-stocks",
            file=sys.stderr,
        )
        return False

    for cfg in MARKETS:
        fn = getattr(ak, cfg["func"], None)
        if fn is None:
            print(f"  [skip] {cfg['market']}: akshare has no function {cfg['func']!r}")
            counts.market_errors += 1
            continue
        try:
            df = fn()
        except Exception as e:  # per-market isolation
            print(f"  [error] {cfg['market']}: {cfg['func']}() failed: {e}")
            counts.market_errors += 1
            continue

        cols = list(df.columns)
        code_col = _first_col(cols, cfg["code_cols"])
        name_col = _first_col(cols, cfg["name_cols"])
        if not code_col or not name_col:
            print(f"  [error] {cfg['market']}: expected columns not found; got {cols}")
            counts.market_errors += 1
            continue

        seen: set[str] = set()
        for _, row in df.iterrows():
            code = _clean_code(row[code_col])
            name = str(row[name_col]).strip()
            if not code or code == "nan" or not name or name == "nan":
                continue
            if cfg.get("zfill"):
                code = code.zfill(cfg["zfill"])
            exchange = cfg.get("exchange") or (
                cfg["exchange_fn"](code) if cfg.get("exchange_fn") else None
            )
            ticker = code  # for these markets ticker == canonical code
            e = upsert_entity(
                session, "stock", code, name,
                ticker=ticker, exchange=exchange,
                country_code=cfg["country_code"],
                dry_run=dry_run, counts=counts,
            )
            upsert_links(session, e, "stock", code, ticker, cfg["market"], source_ids, dry_run, counts)
            seen.add(code)
        mark_delisted(session, cfg["market"], seen, dry_run, counts)
        print(f"  {cfg['market']}: {len(seen)} stocks processed")
    return True


def load_source_ids(session: Session) -> dict[str, int]:
    return {s.name: s.id for s in session.query(DaasSource).all()}


# ════════════════════════════════════════════════════════════════════════
# Cron registration — idempotent on task/schedule name
# ════════════════════════════════════════════════════════════════════════
TASK_NAME = "entity-sync-stocks"
SCHEDULE_NAME = "entity-sync-weekly"
TASK_COMMAND = (
    "uv run --with akshare --directory mcp/daas-mcp python entity_sync.py --sync-stocks"
)
CRON_EXPR = "17 3 * * 1"  # weekly, Mon 03:17 local-ish (off the :00 mark)


def register_cron(session: Session) -> int:
    print("Registering cron task + schedule...")
    task = session.query(Task).filter(Task.name == TASK_NAME).first()
    if task is None:
        task = Task(
            name=TASK_NAME,
            description="Weekly refresh of stock entities + datasource links (akshare → daas.db)",
            command=TASK_COMMAND,
            timeout=1800,
        )
        session.add(task)
        session.commit()
        print(f"  created task '{TASK_NAME}' (id={task.id})")
    else:
        print(f"  task '{TASK_NAME}' already exists (id={task.id}) — left unchanged")

    sched = session.query(Schedule).filter(Schedule.name == SCHEDULE_NAME).first()
    if sched is None:
        sched = Schedule(
            name=SCHEDULE_NAME,
            cron_expr=CRON_EXPR,
            task_name=TASK_NAME,
            timezone=os.environ.get("CRON_TIMEZONE", "UTC"),
            enabled=1,
        )
        session.add(sched)
        session.commit()
        print(f"  created schedule '{SCHEDULE_NAME}' (cron='{CRON_EXPR}', tz={sched.timezone})")
    else:
        print(f"  schedule '{SCHEDULE_NAME}' already exists — left unchanged")

    print(
        "  NOTE: the schedule takes effect on the next cron-mcp start "
        "(cron-mcp loads schedules via load_schedules() at startup)."
    )
    return 0


# ════════════════════════════════════════════════════════════════════════
# Entrypoint
# ════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sync entities (stocks + countries) into daas.db.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--sync-all", action="store_true", help="sync stocks + countries + links")
    g.add_argument("--sync-stocks", action="store_true", help="sync stocks only")
    g.add_argument("--sync-countries", action="store_true", help="sync countries only")
    g.add_argument("--register-cron", action="store_true", help="install weekly refresh task+schedule")
    p.add_argument("--dry-run", action="store_true", help="print the plan; perform no writes")
    p.add_argument("--db-url", help="override DAAS_DATABASE_URL for this run")
    args = p.parse_args(argv)

    if args.db_url:
        os.environ["DAAS_DATABASE_URL"] = args.db_url
        Database._instance = None  # reset singleton so override takes effect

    db = Database()
    session = db.get_session()

    if args.register_cron:
        return register_cron(session)

    do_stocks = args.sync_all or args.sync_stocks
    do_countries = args.sync_all or args.sync_countries
    if not (do_stocks or do_countries):
        p.error("choose one of --sync-all / --sync-stocks / --sync-countries / --register-cron")

    if args.dry_run:
        print("Dry-run plan (no writes):")
    counts = Counts()
    source_ids = load_source_ids(session)
    print(f"Known datasources for link derivation: {sorted(source_ids)}")

    if do_countries:
        sync_countries(session, source_ids, args.dry_run, counts)
    if do_stocks:
        ok = sync_stocks(session, source_ids, args.dry_run, counts)
        if not ok:
            return 1  # missing akshare — already printed the error

    counts.print_summary()
    if args.dry_run:
        print("  (dry-run: nothing was written)")
    else:
        print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
