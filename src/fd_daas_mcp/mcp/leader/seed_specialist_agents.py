"""Seed one default CrewAI specialist agent per enabled data-fetch MCP.

For every enabled row in `leader_upstreams`, upsert a specialist agent named
`<upstream>-agent` bound to that upstream, with a templated role/goal/backstory
and `model="fast"` (the `fast` tier alias → `LEADER_MODEL_FAST`, the data-fetch
default). Re-running updates role/goal/backstory but preserves any per-agent
`model` a user has set (see `preserve_model`).

Idempotent on name. Flags: `--dry-run` (plan, write nothing), `--unseed`
(delete the seeded rows + print a rollback note). Safe to run via:

    uv run --directory mcp/leader-mcp python seed_specialist_agents.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MCP_ROOT = _HERE.parent
if str(_MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCP_ROOT))

from dotenv import load_dotenv

load_dotenv(_MCP_ROOT / ".env")
load_dotenv(_HERE / ".env", override=True)

from gateway_database import get_gateway_db
from workflow_database import get_workflow_db, reset_workflow_db


def _agent_template(upstream: str) -> dict:
    """Role/goal/backstory for a default specialist agent on `upstream`."""
    display = upstream.replace("-", " ").title()
    # registry-based upstreams (yfinance, akshare) expose a dispatch tool
    registry = upstream in ("yfinance", "akshare")
    role = f"{display} data specialist"
    if registry:
        goal = (
            f"Fetch data from the {upstream} MCP. Use search_registry_{upstream} "
            f"to find the right function name, then call_data_mcp_{upstream} with "
            f"the dispatch tool and {{name, params_json}} arguments. Return the "
            f"raw fetched data."
        )
        backstory = (
            f"You are a specialist for the {upstream} data-fetch MCP. You can only "
            f"fetch from this upstream. Use search_registry_{upstream} to discover "
            f"functions, then call_data_mcp_{upstream} to execute them. Always "
            f"return the raw result."
        )
    else:
        goal = (
            f"Fetch data from the {upstream} MCP. Use list_tools_{upstream} to "
            f"see the available tools, then call_data_mcp_{upstream}(tool, arguments) "
            f"to execute the right one. Return the raw fetched data."
        )
        backstory = (
            f"You are a specialist for the {upstream} data-fetch MCP. You can only "
            f"fetch from this upstream. Use list_tools_{upstream} to inspect tools, "
            f"then call_data_mcp_{upstream} to execute. Always return the raw result."
        )
    return {"role": role, "goal": goal, "backstory": backstory}


def _agent_name(upstream: str) -> str:
    return f"{upstream}-agent"


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed default specialist agents.")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; write nothing.")
    parser.add_argument("--unseed", action="store_true", help="Delete seeded agents + print rollback.")
    args = parser.parse_args()

    gw = get_gateway_db()
    reset_workflow_db()
    db = get_workflow_db()

    upstreams = gw.list_upstreams(include_disabled=False)
    if not upstreams:
        print("No enabled leader_upstreams rows found. Run seed_upstreams.py first.")
        return 1

    if args.unseed:
        deleted = []
        for u in upstreams:
            name = _agent_name(u["name"])
            # direct delete by name (no MCP tool for delete; seed owns its rows)
            session = db.get_session()
            try:
                from fd_daas_mcp.models import SpecialistAgent
                row = session.query(SpecialistAgent).filter(SpecialistAgent.name == name).first()
                if row is not None:
                    session.delete(row)
                    session.commit()
                    deleted.append(name)
            finally:
                session.close()
        print(f"Unseeded {len(deleted)} specialist agent(s): {deleted}")
        print("Rollback note: re-run `python seed_specialist_agents.py` to restore them.")
        return 0

    print(f"Planning specialist agents for {len(upstreams)} enabled upstream(s):")
    for u in upstreams:
        name = _agent_name(u["name"])
        tpl = _agent_template(u["name"])
        print(f"  - {name} -> upstream='{u['name']}' role='{tpl['role']}' model=fast")
    if args.dry_run:
        print("--dry-run: wrote nothing.")
        return 0

    upserted = []
    for u in upstreams:
        name = _agent_name(u["name"])
        tpl = _agent_template(u["name"])
        row = db.upsert_specialist_agent(
            name=name,
            upstream=u["name"],
            role=tpl["role"],
            goal=tpl["goal"],
            backstory=tpl["backstory"],
            model="fast",  # fast tier alias (LEADER_MODEL_FAST) — data-fetch default
            enabled=True,
            preserve_model=True,  # don't clobber a user-set model on re-seed
        )
        upserted.append(row["name"])
    print(f"Upserted {len(upserted)} specialist agent(s): {upserted}")
    print("Tip: set a per-agent model with LEADER_MODELS + create_specialist_agent(model=...).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
