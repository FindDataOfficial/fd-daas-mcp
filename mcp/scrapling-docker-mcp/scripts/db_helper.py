#!/usr/bin/env python3
"""Save/query scraw configs in the DAAS scraw database.

Usage:
  python3 db_helper.py save <name> <url> <columns_json>
  python3 db_helper.py list
  python3 db_helper.py get <name>
  python3 db_helper.py delete <name>
"""

import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from init_db import ScrawConfig, Base, get_database_url


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    engine = create_engine(get_database_url(), echo=False)
    Base.metadata.create_all(engine)  # ponytail: auto-create on every run, idempotent

    cmd = sys.argv[1]

    with Session(engine) as session:
        if cmd == "save":
            name = sys.argv[2]
            url = sys.argv[3]
            columns_json = sys.argv[4] if len(sys.argv) > 4 else "[]"
            columns = json.loads(columns_json)

            existing = session.query(ScrawConfig).filter(ScrawConfig.name == name).first()
            if existing:
                existing.url = url
                existing.columns_json = columns
                print(f"Updated: {name}")
            else:
                cfg = ScrawConfig(name=name, url=url, columns_json=columns)
                session.add(cfg)
                print(f"Saved: {name}")
            session.commit()

        elif cmd == "list":
            configs = session.query(ScrawConfig).order_by(ScrawConfig.name).all()
            print(json.dumps([
                {"name": c.name, "url": c.url, "columns": c.columns_json}
                for c in configs
            ], ensure_ascii=False, indent=2))

        elif cmd == "get":
            name = sys.argv[2]
            cfg = session.query(ScrawConfig).filter(ScrawConfig.name == name).first()
            if cfg:
                print(json.dumps({
                    "name": cfg.name, "url": cfg.url, "columns": cfg.columns_json
                }, ensure_ascii=False, indent=2))
            else:
                print(f"Not found: {name}", file=sys.stderr)
                sys.exit(1)

        elif cmd == "delete":
            name = sys.argv[2]
            cfg = session.query(ScrawConfig).filter(ScrawConfig.name == name).first()
            if cfg:
                session.delete(cfg)
                session.commit()
                print(f"Deleted: {name}")
            else:
                print(f"Not found: {name}", file=sys.stderr)
                sys.exit(1)

        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)
            sys.exit(1)


if __name__ == "__main__":
    main()
