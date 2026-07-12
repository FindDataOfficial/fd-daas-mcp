"""Self-check for *script-based* entity-collection rules — temp DB + temp rule
script, no network, no LLM.

Exercises the `rule_script` column added to `entity_collections` and the
`EntityCollectionService` script-runner path end-to-end:

  - create with `rule_script` (path stored in DB, surfaced in to_dict)
  - sync executes the script → members match the script's `members(ctx)` output
  - re-sync after editing the script → add_in / remove_out recorded (source=cron)
  - script return-value normalization: str codes, dict {entity_type,code},
    dict {entity_id}, and unknown-code skipping (sync never fails the whole
    collection over one delisted code)
  - `ctx.query(sql)` reads another daas.db table (a seeded `scraw_*` table) —
    the cross-table power that's the whole point of a script vs rule_json
  - `ctx` is read-only: a write statement raises sqlite3.OperationalError
  - mutual-exclusivity: `rule` + `rule_script` together → ValueError
  - missing-script: `rule_script` pointing at a nonexistent file → FileNotFoundError
  - manual-collection sync no-op (no rule)
  - `--sync-entity-collection <name>` CLI branch works for a script rule
  - `entity_collection_sync.py --sync <name> --dry-run` reports rule_kind=script

Complements `selfcheck_entity_collections.py` (which covers rule_json + CRUD +
cascade + history + cron registration). Run:

    uv run --directory mcp/daas-mcp python selfcheck_entity_collection_script.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from daas_database import Database  # noqa: E402
from registry_service import EntityCollectionService  # noqa: E402
from models import (  # noqa: E402
    Entity,
    EntityCollection,
    EntityCollectionItem,
    EntityCollectionChange,
)

_PASS = 0
_FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ✓ {label}")
    else:
        _FAIL += 1
        print(f"  ✗ {label}  {detail}")


def _seed_entities(session: Session) -> dict:
    ents = [
        Entity(entity_type="stock", code="600519", name="贵州茅台", exchange="SSE", country_code="CN", status="active"),
        Entity(entity_type="stock", code="600036", name="招商银行", exchange="SSE", country_code="CN", status="active"),
        Entity(entity_type="stock", code="000001", name="平安银行", exchange="SZSE", country_code="CN", status="active"),
        Entity(entity_type="country", code="US", name="United States", status="active"),
    ]
    for e in ents:
        session.add(e)
    session.commit()
    return {f"{e.entity_type}:{e.code}": e.id for e in ents}


def _seed_scraw(session: Session) -> None:
    """Seed a `scraw_selfcheck` table so a rule script can prove cross-table
    reads via `ctx.query`. Lives in the same temp DB as the entities."""
    eng = session.bind
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE scraw_selfcheck (code TEXT, amount REAL)"))
        conn.execute(text("INSERT INTO scraw_selfcheck VALUES ('600519', 1.0), ('600036', 2.0)"))


def _write_script(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_create_and_sync_script(session: Session, ids: dict, script_dir: Path) -> None:
    print("[1] Create with rule_script + sync executes the script")
    svc = EntityCollectionService(session)
    script = _write_script(
        script_dir / "sse_stocks.py",
        "def members(ctx):\n"
        "    rows = ctx.query(\"SELECT code FROM entities WHERE entity_type='stock' AND exchange='SSE' ORDER BY code\")\n"
        "    return [r['code'] for r in rows]\n",
    )
    c = svc.create_entity_collection("sse", rule_script=str(script))
    check("create returns rule_script path", c.get("rule_script") == str(script))
    check("create item_count=0 before sync", c["item_count"] == 0)
    # mutual exclusivity on create
    try:
        svc.create_entity_collection("both", rule={"entity_type": "stock"}, rule_script=str(script))
        check("create rule+rule_script rejected", False, "no error")
    except ValueError as e:
        check("create rule+rule_script rejected", "not both" in str(e))
    session.query(EntityCollection).filter(EntityCollection.name == "both").delete()
    session.commit()

    # sync → both SSE stocks added
    r = svc.sync_entity_collection("sse")
    check("sync action=synced", r["action"] == "synced", f"{r}")
    check("sync rule=script", r.get("rule") == "script")
    check("sync added 2 SSE stocks", sorted(r["added"]) == sorted([ids["stock:600519"], ids["stock:600036"]]))
    check("sync removed 0", r["removed"] == [])
    members = svc.list_entity_collection_items("sse")
    check("members count=2 after sync", members["count"] == 2)
    # add_in events recorded with source=cron
    chg = svc.list_entity_collection_changes(collection_name="sse", action="add_in")
    check("2 add_in events recorded", chg["count"] == 2, f"count={chg['count']}")
    check("add_in source=cron", all(c["source"] == "cron" for c in chg["changes"]))


def test_resync_diff(session: Session, ids: dict, script_dir: Path) -> None:
    print("[2] Re-sync after editing the script → add_in/remove_out diff")
    svc = EntityCollectionService(session)
    # rewrite the script: now returns the SZSE stock only (drop both SSE)
    script = script_dir / "sse_stocks.py"
    _write_script(
        script,
        "def members(ctx):\n"
        "    return ['000001']\n",
    )
    r = svc.sync_entity_collection("sse")
    check("resync added SZSE stock", r["added"] == [ids["stock:000001"]])
    check("resync removed both SSE stocks", sorted(r["removed"]) == sorted([ids["stock:600519"], ids["stock:600036"]]))
    members = svc.list_entity_collection_items("sse")
    check("members count=1 after resync", members["count"] == 1)
    # remove_out events recorded
    rem = svc.list_entity_collection_changes(collection_name="sse", action="remove_out")
    check("2 remove_out events recorded", rem["count"] == 2, f"count={rem['count']}")


def test_normalization(session: Session, ids: dict, script_dir: Path) -> None:
    print("[3] Script return-value normalization (str / dict / entity_id / unknown skip)")
    svc = EntityCollectionService(session)
    script = _write_script(
        script_dir / "mixed.py",
        "def members(ctx):\n"
        "    return [\n"
        "        '600519',                                   # str → stock\n"
        "        {'entity_type': 'stock', 'code': '600036'}, # dict → stock\n"
        f"        {{'entity_id': {ids['stock:000001']}}},             # dict → entity_id\n"
        "        '999999',                                   # unknown → skipped\n"
        "    ]\n",
    )
    svc.create_entity_collection("mixed", rule_script=str(script))
    r = svc.sync_entity_collection("mixed")
    check("mixed added 3 resolved stocks", sorted(r["added"]) == sorted([
        ids["stock:600519"], ids["stock:600036"], ids["stock:000001"]
    ]), f"added={r['added']}")
    check("mixed no removals (fresh collection)", r["removed"] == [])


def test_cross_table_read(session: Session, ids: dict, script_dir: Path) -> None:
    print("[4] ctx.query reads another daas.db table (scraw_*)")
    svc = EntityCollectionService(session)
    script = _write_script(
        script_dir / "scraw_read.py",
        "def members(ctx):\n"
        "    rows = ctx.query('SELECT code FROM scraw_selfcheck ORDER BY code')\n"
        "    return [r['code'] for r in rows]\n",
    )
    svc.create_entity_collection("scraw-coll", rule_script=str(script))
    r = svc.sync_entity_collection("scraw-coll")
    check("cross-table read added the 2 scraw codes", sorted(r["added"]) == sorted([
        ids["stock:600519"], ids["stock:600036"]
    ]), f"added={r['added']}")


def test_readonly(session: Session, script_dir: Path) -> None:
    print("[5] ctx is read-only — a write statement raises")
    svc = EntityCollectionService(session)
    script = _write_script(
        script_dir / "readonly.py",
        "def members(ctx):\n"
        "    try:\n"
        "        ctx.query(\"INSERT INTO entities (code) VALUES ('HACK')\")\n"
        "        return {'wrote': True}\n"
        "    except Exception as e:\n"
        "        return {'wrote': False, 'err': str(e)[:40]}\n",
    )
    svc.create_entity_collection("ro-test", rule_script=str(script))
    # sync should not raise; the script catches the error itself and returns a dict
    # (which doesn't resolve to any entity → no members). The point: no row was inserted.
    svc.sync_entity_collection("ro-test")
    hacked = (
        session.query(Entity)
        .filter(Entity.code == "HACK")
        .count()
    )
    check("no row inserted by the script", hacked == 0, f"hacked={hacked}")
    # the script's returned dict should be skipped (not a resolvable item)
    check("script dict return skipped (0 members)", svc.list_entity_collection_items("ro-test")["count"] == 0)


def test_missing_script(session: Session) -> None:
    print("[6] Missing rule script → FileNotFoundError")
    svc = EntityCollectionService(session)
    svc.create_entity_collection("missing", rule_script="/no/such/script.py")
    try:
        svc.sync_entity_collection("missing")
        check("missing script raises", False, "no error")
    except FileNotFoundError as e:
        check("missing script raises FileNotFoundError", "not found" in str(e).lower())


def test_manual_noop(session: Session) -> None:
    print("[7] Manual collection (no rule) sync is a no-op")
    svc = EntityCollectionService(session)
    svc.create_entity_collection("manual")
    r = svc.sync_entity_collection("manual")
    check("manual → action=manual_collection", r["action"] == "manual_collection")
    check("manual → unchanged=0", r["unchanged"] == 0)


def test_update_rule_script(session: Session, script_dir: Path) -> None:
    print("[8] update_entity_collection switches rule_script + clears rule_json")
    svc = EntityCollectionService(session)
    # start with a json rule
    svc.create_entity_collection("switch", rule={"entity_type": "stock", "exchange": "SSE"})
    check("switch has rule_json", svc.get_entity_collection("switch")["rule"] is not None)
    check("switch has no rule_script", svc.get_entity_collection("switch")["rule_script"] is None)
    # switch to a script rule → rule_json cleared
    script = _write_script(script_dir / "switch.py", "def members(ctx):\n    return ['600519']\n")
    svc.update_entity_collection("switch", rule_script=str(script))
    g = svc.get_entity_collection("switch")
    check("after update rule_script set", g["rule_script"] == str(script))
    check("after update rule_json cleared (mutually exclusive)", g["rule"] is None)
    # clear_rule resets both
    svc.update_entity_collection("switch", clear_rule=True)
    g2 = svc.get_entity_collection("switch")
    check("clear_rule resets rule_json", g2["rule"] is None)
    check("clear_rule resets rule_script", g2["rule_script"] is None)
    # mutual exclusivity on update
    try:
        svc.update_entity_collection("switch", rule={"entity_type": "stock"}, rule_script=str(script))
        check("update rule+rule_script rejected", False, "no error")
    except ValueError:
        check("update rule+rule_script rejected", True)


def test_cli_branch(session: Session, ids: dict, db_url: str, script_dir: Path) -> None:
    print("[9] `--sync-entity-collection <name>` CLI branch (script rule)")
    svc = EntityCollectionService(session)
    script = _write_script(script_dir / "cli.py", "def members(ctx):\n    return ['600519', '600036']\n")
    svc.create_entity_collection("cli-script", rule_script=str(script))
    env = dict(os.environ)
    here = Path(__file__).resolve().parent
    r = subprocess.run(
        ["uv", "run", "--directory", str(here), "python", "server.py",
         "--sync-entity-collection", "cli-script"],
        capture_output=True, text=True, env=env, timeout=120,
    )
    out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        parsed = {}
    check("CLI branch exit 0", r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:200]}")
    check("CLI branch action=synced", parsed.get("action") == "synced", f"{out[:200]}")
    check("CLI branch rule=script", parsed.get("rule") == "script", f"{out[:200]}")
    check("CLI branch added 2 stocks", sorted(parsed.get("added", [])) == sorted([ids["stock:600519"], ids["stock:600036"]]))


def test_dry_run(session: Session, script_dir: Path) -> None:
    print("[10] `entity_collection_sync.py --sync <name> --dry-run` (script rule)")
    svc = EntityCollectionService(session)
    script = _write_script(script_dir / "dry.py", "def members(ctx):\n    return ['600519']\n")
    svc.create_entity_collection("dry-script", rule_script=str(script))
    env = dict(os.environ)
    here = Path(__file__).resolve().parent
    r = subprocess.run(
        ["uv", "run", "--directory", str(here), "python", "entity_collection_sync.py",
         "--sync", "dry-script", "--dry-run"],
        capture_output=True, text=True, env=env, timeout=120,
    )
    out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        parsed = {}
    check("dry-run exit 0", r.returncode == 0, f"stderr={r.stderr[:200]}")
    check("dry-run rule_kind=script", parsed.get("rule_kind") == "script", f"{out[:200]}")
    check("dry-run surfaces rule_script path", bool(parsed.get("rule_script")), f"{out[:200]}")
    check("dry-run intended_members=1", parsed.get("intended_members") == 1, f"{out[:200]}")
    check("dry-run note=writes performed", "no writes performed" in parsed.get("note", ""), f"{out[:200]}")


def main() -> int:
    db_dir = tempfile.mkdtemp(prefix="ecs-selfcheck-")
    db_path = os.path.join(db_dir, "daas.db")
    os.environ["DAAS_DATABASE_URL"] = f"sqlite:///{db_path}"
    Database._instance = None  # reset singleton so the temp DB takes effect
    db = Database()
    session = db.get_session()
    script_dir = Path(db_dir) / "rules"
    script_dir.mkdir(parents=True, exist_ok=True)

    print(f"Self-check: entity-collection script rules (temp DB: {db_path})")
    ids = _seed_entities(session)
    _seed_scraw(session)

    test_create_and_sync_script(session, ids, script_dir)
    test_resync_diff(session, ids, script_dir)
    test_normalization(session, ids, script_dir)
    test_cross_table_read(session, ids, script_dir)
    test_readonly(session, script_dir)
    test_missing_script(session)
    test_manual_noop(session)
    test_update_rule_script(session, script_dir)
    test_cli_branch(session, ids, f"sqlite:///{db_path}", script_dir)
    test_dry_run(session, script_dir)

    print(f"\n{_PASS} passed, {_FAIL} failed")
    try:
        session.close()
    except Exception:
        pass
    import shutil
    shutil.rmtree(db_dir, ignore_errors=True)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
