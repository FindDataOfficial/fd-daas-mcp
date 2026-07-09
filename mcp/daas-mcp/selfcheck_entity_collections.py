"""Self-check for entity collections — temp DB, no network, no LLM.

Exercises the full EntityCollectionService surface + the
`--sync-entity-collection` server CLI branch + the `entity_collection_sync.py`
script, against an isolated temp DB:

  - fresh-DB table creation (Base.metadata.create_all)
  - cascade on collection delete + on entity delete
  - create / list / get / update / delete
  - add / remove with change recording (add_in / remove_out, source=manual)
  - re-add no-op (already_member), remove non-member no-op (not_member)
  - reorder + unknown-id rejection
  - history query + filters (collection / entity / action / source)
  - rule-based sync (add / remove / idempotent)
  - manual-collection sync no-op
  - `--sync-entity-collection` CLI branch happy path + missing-collection error
  - `entity_collection_sync.py --sync` + `--register-cron` idempotency

Run:
    uv run --directory mcp/daas-mcp python selfcheck_entity_collections.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Make sibling modules importable when invoked via `uv run ... python`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from daas_database import Database  # noqa: E402
from registry_service import EntityCollectionService  # noqa: E402
from models import Entity, EntityCollection, EntityCollectionItem, EntityCollectionChange  # noqa: E402

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
    """Seed 4 entities: 3 stocks (2 SSE, 1 SZSE) + 1 country."""
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


def test_table_creation(session: Session) -> None:
    print("[1] Fresh-DB table creation")
    eng = session.bind
    with eng.connect() as conn:
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    names = {r[0] for r in rows}
    check("entity_collections created", "entity_collections" in names)
    check("entity_collection_items created", "entity_collection_items" in names)
    check("entity_collection_changes created", "entity_collection_changes" in names)


def test_cascade(session: Session, ids: dict) -> None:
    print("[2] Cascade on delete")
    svc = EntityCollectionService(session)
    svc.create_entity_collection("cas-coll")
    svc.add_entity_to_collection("cas-coll", entity_id=ids["stock:600519"], reason="r")
    n_items = session.query(EntityCollectionItem).count()
    n_chg = session.query(EntityCollectionChange).count()
    check("member + change recorded before delete", n_items == 1 and n_chg == 1, f"items={n_items} chg={n_chg}")
    # delete collection → cascade
    svc.delete_entity_collection("cas-coll")
    n_items = session.query(EntityCollectionItem).count()
    n_chg = session.query(EntityCollectionChange).count()
    check("collection delete cascades to items + changes", n_items == 0 and n_chg == 0, f"items={n_items} chg={n_chg}")

    # entity delete cascade — use a throwaway entity so seeded ids stay valid
    svc.create_entity_collection("cas-coll2")
    throwaway = Entity(entity_type="stock", code="900001", name="Throwaway", exchange="SSE", country_code="CN", status="active")
    session.add(throwaway)
    session.commit()
    svc.add_entity_to_collection("cas-coll2", entity_id=throwaway.id, reason="r")
    eid = throwaway.id
    e = session.get(Entity, eid)
    session.delete(e)
    session.commit()
    remaining = (
        session.query(EntityCollectionItem)
        .filter(EntityCollectionItem.entity_id == eid)
        .count()
    )
    check("entity delete cascades to its membership rows", remaining == 0, f"remaining={remaining}")
    # cleanup
    svc.delete_entity_collection("cas-coll2")


def test_crud(session: Session) -> None:
    print("[3] CRUD: create / list / get / update / delete")
    svc = EntityCollectionService(session)
    c = svc.create_entity_collection("crud1", description="d1")
    check("create returns id+name", c.get("id") and c["name"] == "crud1")
    check("create item_count=0", c["item_count"] == 0)
    # duplicate
    try:
        svc.create_entity_collection("crud1")
        check("duplicate name rejected", False, "no error raised")
    except ValueError as e:
        check("duplicate name rejected", "already exists" in str(e))
    # list
    lst = svc.list_entity_collections()
    check("list includes crud1", any(x["name"] == "crud1" for x in lst))
    # get
    g = svc.get_entity_collection("crud1")
    check("get returns members=[]", g.get("members") == [])
    # update description
    svc.update_entity_collection("crud1", description="d2")
    check("update description", svc.get_entity_collection("crud1")["description"] == "d2")
    # update name (rename)
    svc.update_entity_collection("crud1", new_name="crud1b")
    check("rename", svc.get_entity_collection("crud1b")["name"] == "crud1b")
    # rename collision
    svc.create_entity_collection("crud2")
    try:
        svc.update_entity_collection("crud2", new_name="crud1b")
        check("rename collision rejected", False, "no error")
    except ValueError:
        check("rename collision rejected", True)
    # update with no fields → error
    try:
        svc.update_entity_collection("crud1b")
        check("update no-fields rejected", False, "no error")
    except ValueError:
        check("update no-fields rejected", True)
    # delete
    svc.delete_entity_collection("crud1b")
    svc.delete_entity_collection("crud2")
    check("delete removed", len(svc.list_entity_collections()) == 0)


def test_membership(session: Session, ids: dict) -> None:
    print("[4] Membership: add / remove / re-add / not-member + change recording")
    svc = EntityCollectionService(session)
    svc.create_entity_collection("m1")
    # add by id
    r = svc.add_entity_to_collection("m1", entity_id=ids["stock:600519"], reason="pick")
    check("add by id → added", r["action"] == "added")
    # add by (type, code)
    r = svc.add_entity_to_collection("m1", entity_type="stock", code="000001")
    check("add by (type, code) → added", r["action"] == "added")
    # re-add no-op
    r = svc.add_entity_to_collection("m1", entity_id=ids["stock:600519"])
    check("re-add → already_member (no-op)", r["action"] == "already_member")
    # entity not found
    try:
        svc.add_entity_to_collection("m1", entity_type="stock", code="ZZZZZZ")
        check("add unknown entity → error", False, "no error")
    except ValueError:
        check("add unknown entity → error", True)
    # members ordered
    lst = svc.list_entity_collection_items("m1")
    check("members ordered by sort_order", [m["sort_order"] for m in lst["members"]] == [0, 1])
    check("members carry entity detail", lst["members"][0]["code"] == "600519")
    # change log records 2 add_in (re-add did NOT record a 3rd)
    chg = svc.list_entity_collection_changes("m1")
    actions = [c["action"] for c in chg["changes"]]
    check("history has exactly 2 add_in (no-op recorded nothing)", actions == ["add_in", "add_in"], f"{actions}")
    # remove
    r = svc.remove_entity_from_collection("m1", entity_id=ids["stock:600519"], reason="delisted")
    check("remove → removed", r["action"] == "removed")
    # re-remove no-op
    r = svc.remove_entity_from_collection("m1", entity_id=ids["stock:600519"])
    check("re-remove → not_member (no-op)", r["action"] == "not_member")
    # history now has add_in, add_in, remove_out (newest first)
    chg = svc.list_entity_collection_changes("m1")
    actions = [c["action"] for c in chg["changes"]]
    check("history after remove = [remove_out, add_in, add_in]", actions == ["remove_out", "add_in", "add_in"], f"{actions}")
    check("remove_out source=manual", chg["changes"][0]["source"] == "manual")
    svc.delete_entity_collection("m1")


def test_reorder(session: Session, ids: dict) -> None:
    print("[5] Reorder + unknown-id rejection")
    svc = EntityCollectionService(session)
    svc.create_entity_collection("r1")
    for eid in [ids["stock:600519"], ids["stock:600036"], ids["stock:000001"]]:
        svc.add_entity_to_collection("r1", entity_id=eid)
    items = svc.list_entity_collection_items("r1")["members"]
    ordered = [items[2]["id"], items[0]["id"], items[1]["id"]]  # reverse-ish
    svc.reorder_entity_collection_items("r1", ordered)
    after = [m["id"] for m in svc.list_entity_collection_items("r1")["members"]]
    check("reorder applied", after == ordered, f"{after}")
    # unknown id
    try:
        svc.reorder_entity_collection_items("r1", [999999])
        check("reorder unknown id rejected", False, "no error")
    except ValueError:
        check("reorder unknown id rejected", True)
    # wrong count
    try:
        svc.reorder_entity_collection_items("r1", [items[0]["id"]])
        check("reorder wrong count rejected", False, "no error")
    except ValueError:
        check("reorder wrong count rejected", True)
    svc.delete_entity_collection("r1")


def test_history_filters(session: Session, ids: dict) -> None:
    print("[6] History query + filters")
    svc = EntityCollectionService(session)
    svc.create_entity_collection("h1")
    svc.add_entity_to_collection("h1", entity_id=ids["stock:600519"])
    svc.add_entity_to_collection("h1", entity_id=ids["stock:000001"])
    svc.remove_entity_from_collection("h1", entity_id=ids["stock:600519"])
    # filter by action
    adds = svc.list_entity_collection_changes("h1", action="add_in")
    check("filter action=add_in → 2", adds["count"] == 2, f"{adds['count']}")
    rems = svc.list_entity_collection_changes("h1", action="remove_out")
    check("filter action=remove_out → 1", rems["count"] == 1)
    # filter by entity
    e_chg = svc.list_entity_collection_changes(entity_id=ids["stock:600519"])
    check("filter by entity → 2 (add+remove)", e_chg["count"] == 2, f"{e_chg['count']}")
    # enrich: entity code/name present
    check("history enriched with entity_code", e_chg["changes"][0].get("entity_code") is not None)
    check("history enriched with collection_name", e_chg["changes"][0].get("collection_name") == "h1" or e_chg["changes"][1].get("collection_name") == "h1")
    # invalid action
    try:
        svc.list_entity_collection_changes("h1", action="bogus")
        check("invalid action rejected", False, "no error")
    except ValueError:
        check("invalid action rejected", True)
    svc.delete_entity_collection("h1")


def test_sync(session: Session, ids: dict) -> None:
    print("[7] Rule-based sync: add / remove / idempotent + manual no-op")
    svc = EntityCollectionService(session)
    # rule-based: SSE stocks (600519, 600036)
    svc.create_entity_collection("sync-sse", rule={"entity_type": "stock", "exchange": "SSE"})
    r = svc.sync_entity_collection("sync-sse")
    check("sync adds SSE stocks", sorted(r["added"]) == sorted([ids["stock:600519"], ids["stock:600036"]]), f"{r['added']}")
    check("sync unchanged=0", r["unchanged"] == 0)
    # idempotent re-sync
    r = svc.sync_entity_collection("sync-sse")
    check("re-sync idempotent (no add/remove)", r["added"] == [] and r["removed"] == [])
    # changes recorded with source=cron
    chg = svc.list_entity_collection_changes("sync-sse", source="cron")
    check("sync changes recorded source=cron", chg["count"] == 2, f"{chg['count']}")
    # now narrow the rule to only 600519 → 600036 should be removed
    svc.update_entity_collection("sync-sse", rule={"entity_type": "stock", "exchange": "SSE", "codes": ["600519"]})
    r = svc.sync_entity_collection("sync-sse")
    check("sync removes non-match after rule narrows", r["removed"] == [ids["stock:600036"]], f"{r['removed']}")
    check("sync keeps match", r["unchanged"] == 1)
    # remove_out recorded with source=cron
    chg = svc.list_entity_collection_changes("sync-sse", action="remove_out", source="cron")
    check("remove_out source=cron recorded", chg["count"] == 1)
    # manual collection sync = no-op
    svc.create_entity_collection("sync-manual")
    svc.add_entity_to_collection("sync-manual", entity_id=ids["stock:000001"])
    r = svc.sync_entity_collection("sync-manual")
    check("manual collection sync → manual_collection no-op", r["action"] == "manual_collection" and r["added"] == [] and r["removed"] == [])
    check("manual sync unchanged=1", r["unchanged"] == 1)
    # name_regex rule (uses registered REGEXP)
    svc.create_entity_collection("sync-regex", rule={"entity_type": "stock", "name_regex": "茅台$"})
    r = svc.sync_entity_collection("sync-regex")
    check("name_regex rule matches 茅台", r["added"] == [ids["stock:600519"]], f"{r['added']}")
    for n in ("sync-sse", "sync-manual", "sync-regex"):
        svc.delete_entity_collection(n)


def test_cli_branch(session: Session, ids: dict, db_url: str) -> None:
    print("[8] `--sync-entity-collection` CLI branch")
    svc = EntityCollectionService(session)
    svc.create_entity_collection("cli-sse", rule={"entity_type": "stock", "exchange": "SSE"})
    # happy path
    env = dict(os.environ)
    r = subprocess.run(
        ["uv", "run", "--directory", str(Path(__file__).resolve().parent),
         "python", "server.py", "--sync-entity-collection", "cli-sse"],
        capture_output=True, text=True, env=env, timeout=120,
    )
    out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        parsed = {}
    check("CLI branch exit 0", r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:200]}")
    check("CLI branch prints sync summary", parsed.get("action") == "synced", f"{out[:200]}")
    check("CLI branch added SSE stocks", sorted(parsed.get("added", [])) == sorted([ids["stock:600519"], ids["stock:600036"]]))
    # missing collection
    r2 = subprocess.run(
        ["uv", "run", "--directory", str(Path(__file__).resolve().parent),
         "python", "server.py", "--sync-entity-collection", "no-such-collection"],
        capture_output=True, text=True, env=env, timeout=120,
    )
    out2 = r2.stdout.strip().splitlines()[-1] if r2.stdout.strip() else ""
    try:
        parsed2 = json.loads(out2)
    except json.JSONDecodeError:
        parsed2 = {}
    check("CLI branch missing collection → non-zero exit", r2.returncode != 0, f"rc={r2.returncode}")
    check("CLI branch missing collection → error in JSON", "error" in parsed2, f"{out2[:200]}")
    svc.delete_entity_collection("cli-sse")


def test_sync_script_register(session: Session, ids: dict) -> None:
    print("[9] `entity_collection_sync.py --register-cron` idempotency")
    svc = EntityCollectionService(session)
    svc.create_entity_collection("regtest", rule={"entity_type": "stock", "exchange": "SSE"})
    env = dict(os.environ)
    here = Path(__file__).resolve().parent
    r1 = subprocess.run(
        ["uv", "run", "--directory", str(here), "python", "entity_collection_sync.py", "--register-cron", "regtest"],
        capture_output=True, text=True, env=env, timeout=120,
    )
    check("register-cron exit 0", r1.returncode == 0, f"stderr={r1.stderr[:200]}")
    check("register-cron created task", "created task" in r1.stdout)
    check("register-cron created schedule", "created schedule" in r1.stdout)
    # idempotent re-register
    r2 = subprocess.run(
        ["uv", "run", "--directory", str(here), "python", "entity_collection_sync.py", "--register-cron", "regtest"],
        capture_output=True, text=True, env=env, timeout=120,
    )
    check("re-register says already exists", "already exists" in r2.stdout, f"{r2.stdout[:300]}")
    # unregister
    r3 = subprocess.run(
        ["uv", "run", "--directory", str(here), "python", "entity_collection_sync.py", "--unregister-cron", "regtest"],
        capture_output=True, text=True, env=env, timeout=120,
    )
    check("unregister-cron exit 0", r3.returncode == 0)
    check("unregister removed rows", "removed" in r3.stdout)
    svc.delete_entity_collection("regtest")


def main() -> int:
    db_dir = tempfile.mkdtemp(prefix="ec-selfcheck-")
    db_path = os.path.join(db_dir, "daas.db")
    os.environ["DAAS_DATABASE_URL"] = f"sqlite:///{db_path}"
    Database._instance = None  # reset singleton
    db = Database()
    session = db.get_session()

    print(f"Self-check: entity collections (temp DB: {db_path})")
    ids = _seed_entities(session)

    test_table_creation(session)
    test_cascade(session, ids)
    test_crud(session)
    test_membership(session, ids)
    test_reorder(session, ids)
    test_history_filters(session, ids)
    test_sync(session, ids)
    test_cli_branch(session, ids, f"sqlite:///{db_path}")
    test_sync_script_register(session, ids)

    print(f"\n{_PASS} passed, {_FAIL} failed")
    # cleanup
    try:
        session.close()
    except Exception:
        pass
    import shutil
    shutil.rmtree(db_dir, ignore_errors=True)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
