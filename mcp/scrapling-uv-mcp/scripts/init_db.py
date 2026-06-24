#!/usr/bin/env python3
"""Initialize the DAAS scraw database. Creates tables if they don't exist.

Usage: python3 init_db.py
"""

import os
import sys
from pathlib import Path

from sqlalchemy import Column, Integer, String, JSON, DateTime, create_engine, func
from sqlalchemy.orm import declarative_base, Session

Base = declarative_base()


class ScrawConfig(Base):
    __tablename__ = "scraw_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False)
    name = Column(String(255), nullable=False)
    columns_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


def get_database_url():
    # ponytail: .env lives at scrapling-uv-mcp root (parent of scripts/)
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key.strip() == "DAAS_SCRAW_DATABASE_URL":
                    return val.strip().strip('"').strip("'")
    return os.environ.get("DAAS_SCRAW_DATABASE_URL", "sqlite:///../daas.db")


def main():
    url = get_database_url()
    print(f"Database: {url}")

    engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)
    print("Tables created (if not exists).")

    with Session(engine) as session:
        count = session.query(ScrawConfig).count()
        print(f"Existing configs: {count}")


if __name__ == "__main__":
    main()
