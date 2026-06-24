---
name: fd-daas-mcp-creator
description: |
  Generate a SQLAlchemy-backed database registry for any CLI-Anything harness.
  Reads the harness's existing JSON registry, creates SQLAlchemy models (Function
  + FunctionColumn), a Database singleton, a RegistryService that replaces
  registry.py, a MigrationRunner to import JSON→DB, updates setup.py, and
  writes pytest tests. Use this skill when the user wants to add database
  storage to a CLI-Anything harness, migrate a JSON registry to SQLite/PostgreSQL,
  or create a DAAS/MCP data layer. Triggers on phrases like "add database to this
  harness", "migrate registry to SQLite", "create MCP data layer", "generate
  SQLAlchemy models for the harness", "store harness data in a database", or
  when working in a `cli-anything-*` or `*-agent-harness` directory and the user
  mentions SQLite, database, or persistence.
---

# FD-DAAS-MCP Creator

Generate a SQLAlchemy-backed database registry for any CLI-Anything harness.

This skill takes an existing harness (which has a JSON `registry.json` with function metadata) and adds a full SQLAlchemy data layer, replacing the JSON storage with a database. The schema is standardized: every harness gets the same two-table design (`functions` + `function_columns`), making all harnesses queryable the same way.

## Prerequisites

The target harness must already exist with:
- `cli_anything/<name>/core/registry.py` — existing JSON-based registry
- `cli_anything/<name>/metadata/registry.json` — the JSON function catalog
- `setup.py` — the harness package config
- `cli_anything/<name>/tests/` — existing test directory

## What gets generated

| File | Purpose |
|------|---------|
| `cli_anything/<name>/core/models.py` | `Function` + `FunctionColumn` SQLAlchemy models (same schema every harness) |
| `cli_anything/<name>/core/database.py` | `Database` singleton — reads `<NAME>_DATABASE_URL` env var, defaults to SQLite |
| `cli_anything/<name>/core/registry.py` | **Rewritten** — `RegistryService` class + backward-compatible module functions |
| `cli_anything/<name>/core/migrate_registry.py` | `MigrationRunner` — idempotent JSON→DB import with verification |
| `cli_anything/<name>/core/proxy.py` | `ProxyController` — HTTP proxy management (set, enable/disable, persist to JSON) |
| `cli_anything/<name>/core/runner.py` | **Updated** — `call_akshare_function` accepts optional `proxy` parameter |
| `cli_anything/<name>/<name>_cli.py` | **Updated** — `proxy` command group + `--proxy/--no-proxy` flag on `call` |
| `cli_anything/<name>/tests/test_sqlite_registry.py` | 38 pytest tests (models, database, registry, migration) |
| `setup.py` | **Updated** — adds `sqlalchemy>=1.4` to `install_requires` |

## Schema (fixed — same for every harness)

```
functions                        function_columns
├── id (PK, autoincrement)       ├── id (PK, autoincrement)
├── command (unique, indexed)    ├── function_id (FK → functions.id, CASCADE)
├── category                     ├── column_name
├── source                       ├── column_type
├── description                  └── column_description
└── parameters (JSON)
```

## Workflow

### Step 1: Discover the harness

Find the harness root. Look for `setup.py` in the current directory or nearby. Read it to extract the package name and the `cli_anything.<name>` module path. Confirm with the user which harness to modify.

### Step 2: Read the existing registry

Read `cli_anything/<name>/metadata/registry.json` to understand the data shape. Confirm that each entry has `category`, `description`, `source`, `parameters`, and `columns` fields — the standard AKShare-style registry format. If the format differs, adapt the migration logic accordingly and tell the user what you changed.

### Step 3: Generate the files

Write all 5 new files and update `setup.py`. Use the exact patterns below — they're proven across the akshare harness and work with SQLAlchemy 1.4+ and 2.0.

#### models.py

```python
"""
SQLAlchemy models for <harness-name> function registry.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Function(Base):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(255), nullable=False, default="未分类")
    source = Column(String(512), nullable=True)
    description = Column(String, nullable=True)
    parameters = Column(JSON, nullable=True)

    columns = relationship(
        "FunctionColumn",
        back_populates="function",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def toDict(self) -> dict:
        return {
            "command": self.command,
            "category": self.category,
            "source": self.source,
            "description": self.description,
            "parameters": self.parameters or [],
            "columns": [c.toDict() for c in self.columns] if self.columns else [],
        }


class FunctionColumn(Base):
    __tablename__ = "function_columns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    function_id = Column(
        Integer,
        ForeignKey("functions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name = Column(String(255), nullable=False)
    column_type = Column(String(64), nullable=True)
    column_description = Column(String, nullable=True)

    function = relationship("Function", back_populates="columns")

    def toDict(self) -> dict:
        return {
            "name": self.column_name,
            "type": self.column_type,
            "description": self.column_description,
        }
```

#### database.py

Replace `akshare` with the actual harness module name. The `_DEFAULT_DB_DIR` should point to `<module>/metadata/`.

```python
"""
Database module for <harness-name> registry.
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from cli_anything.<name>.core.models import Base

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "metadata"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "registry.db"


class Database:
    """SQLAlchemy engine and session factory.

    Reads <NAME>_DATABASE_URL env var; defaults to SQLite at metadata/registry.db.
    """

    def __init__(self, database_url: Optional[str] = None):
        if database_url is None:
            database_url = os.environ.get(
                "<NAME>_DATABASE_URL",
                f"sqlite:///{_DEFAULT_DB_PATH}",
            )
        self._database_url = database_url
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

    @property
    def database_url(self) -> str:
        return self._database_url

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self.init_db()
        assert self._engine is not None
        return self._engine

    def get_session(self) -> Session:
        if self._session_factory is None:
            self.init_db()
        assert self._session_factory is not None
        return self._session_factory()

    def init_db(self) -> None:
        self._engine = create_engine(
            self._database_url,
            echo=False,
            connect_args=(
                {"check_same_thread": False}
                if self._database_url.startswith("sqlite")
                else {}
            ),
        )
        self._session_factory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)
        logger.info("Database initialized: %s", self._database_url)

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None


_database: Optional[Database] = None


def get_database(database_url: Optional[str] = None) -> Database:
    global _database
    if _database is None:
        _database = Database(database_url)
        _database.init_db()
    return _database


def reset_database() -> None:
    global _database
    if _database is not None:
        _database.dispose()
    _database = None
```

The env var name should be `<UPPERCASE_NAME>_DATABASE_URL` (e.g., `AKSHARE_DATABASE_URL`, `MINIMAX_DATABASE_URL`).

#### registry.py (rewrite)

Replace the existing `registry.py` entirely. Keep backward-compatible module-level functions so the CLI (`akshare_cli.py` etc.) doesn't need changes.

```python
"""
Registry module for <harness-name> function metadata.

Backed by SQLAlchemy database (default SQLite, swappable via DATABASE_URL).
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from cli_anything.<name>.core.models import Function, FunctionColumn

logger = logging.getLogger(__name__)


class RegistryService:
    def __init__(self, session: Session):
        self._session = session

    def list_functions(self, category: Optional[str] = None) -> dict[str, dict]:
        query = self._session.query(Function)
        if category:
            query = query.filter(Function.category == category)
        results = {}
        for func in query.order_by(Function.command).all():
            results[func.command] = func.toDict()
        return results

    def search_functions(self, query: str) -> dict[str, dict]:
        q = f"%{query}%"
        rows = (
            self._session.query(Function)
            .filter(
                or_(Function.command.like(q), Function.category.like(q), Function.description.like(q))
            )
            .order_by(Function.command)
            .all()
        )
        return {func.command: func.toDict() for func in rows}

    def get_function_info(self, name: str) -> Optional[dict]:
        func = self._session.query(Function).filter(Function.command == name).first()
        if func is None:
            return None
        return func.toDict()

    def get_categories(self) -> dict[str, int]:
        rows = (
            self._session.query(Function.category, func.count(Function.id).label("cnt"))
            .group_by(Function.category)
            .order_by(func.count(Function.id).desc())
            .all()
        )
        return {row.category: row.cnt for row in rows}

    def get_category_functions(self, category: str) -> dict[str, dict]:
        return self.list_functions(category=category)


# Backward-compatible module-level API
def _get_service() -> RegistryService:
    from cli_anything.<name>.core.database import get_database
    db = get_database()
    return RegistryService(db.get_session())


def get_registry() -> dict[str, dict]:
    return _get_service().list_functions()

def list_functions(category=None):
    return _get_service().list_functions(category)

def search_functions(query):
    return _get_service().search_functions(query)

def get_function_info(name):
    return _get_service().get_function_info(name)

def get_categories():
    return _get_service().get_categories()

def get_category_functions(category):
    return _get_service().get_category_functions(category)
```

#### migrate_registry.py

```python
"""
Migration runner for importing registry.json into the SQLAlchemy database.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from cli_anything.<name>.core.models import Function, FunctionColumn

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY_DIR = Path(__file__).resolve().parent.parent / "metadata"
_DEFAULT_REGISTRY_PATH = _DEFAULT_REGISTRY_DIR / "registry.json"


class MigrationRunner:
    """Idempotent JSON→DB importer."""

    def __init__(self, session: Session, registry_path: Optional[str] = None):
        self._session = session
        self._registry_path = registry_path or str(_DEFAULT_REGISTRY_PATH)

    def run(self) -> None:
        print(f"Reading registry from: {self._registry_path}")
        data = self._parse_registry()
        print(f"Parsed {len(data)} functions from registry.json")

        imported = 0
        skipped = 0
        total_columns = 0

        for command, info in data.items():
            func = self._upsert_function(command, info)
            if func is None:
                skipped += 1
                continue
            col_count = self._upsert_columns(func, info.get("columns", []))
            total_columns += col_count
            imported += 1

        self._session.flush()
        print(f"Imported: {imported} functions, {total_columns} columns")
        if skipped:
            print(f"Skipped: {skipped} functions")

        ok = self._verify(expected_count=len(data))
        if ok:
            print("Verification PASSED: row counts match")
        else:
            print("Verification FAILED: row counts do not match!")
            sys.exit(1)

    def _parse_registry(self) -> dict[str, dict]:
        with open(self._registry_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _upsert_function(self, command: str, data: dict) -> Optional[Function]:
        if not command:
            return None
        func = self._session.query(Function).filter(Function.command == command).first()
        if func is None:
            func = Function(command=command)
        func.category = data.get("category", "未分类")
        func.source = data.get("source", "")
        func.description = data.get("description", "")
        func.parameters = data.get("parameters", [])
        self._session.add(func)
        self._session.flush()
        return func

    def _upsert_columns(self, func: Function, columns: list[dict]) -> int:
        self._session.query(FunctionColumn).filter(
            FunctionColumn.function_id == func.id
        ).delete()
        count = 0
        for col_data in columns:
            col = FunctionColumn(
                function_id=func.id,
                column_name=col_data.get("name", ""),
                column_type=col_data.get("type", ""),
                column_description=col_data.get("description", ""),
            )
            self._session.add(col)
            count += 1
        return count

    def _verify(self, expected_count: int) -> bool:
        db_count = self._session.query(Function).count()
        db_col_count = self._session.query(FunctionColumn).count()
        print(f"Database: {db_count} functions, {db_col_count} columns")
        print(f"Expected: {expected_count} functions")
        return db_count == expected_count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate registry.json to SQLAlchemy database")
    parser.add_argument("registry_path", nargs="?", default=str(_DEFAULT_REGISTRY_PATH))
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    from cli_anything.<name>.core.database import get_database

    db = get_database(args.database_url)
    session = db.get_session()
    try:
        runner = MigrationRunner(session, args.registry_path)
        runner.run()
        session.commit()
        print("Migration complete.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        db.dispose()
```

#### test_sqlite_registry.py

Write the full test file (38 tests). Read the reference from `akshare-agent-harness/cli_anything/akshare/tests/test_sqlite_registry.py` for the exact content — it's the same pattern for every harness. Replace `akshare` with the harness module name throughout.

Key fixtures:
- `engine` — in-memory SQLite engine
- `session` — session bound to engine
- `populated_session` — 4 pre-populated functions with columns
- `reset_db_singleton` — autouse fixture to reset the Database singleton
- `fake_registry_json` — temp JSON for migration tests

Test classes: `TestFunctionModel` (6), `TestFunctionColumnModel` (3), `TestDatabase` (7), `TestRegistryService` (13), `TestMigrationRunner` (9).

#### setup.py update

Add `"sqlalchemy>=1.4"` to the `install_requires` list. Use Edit to make the minimal change.

### Step 4: Install and run migration

```bash
cd <harness-root>
uv pip install -e ".[dev]"
uv run python -m cli_anything.<name>.core.migrate_registry
```

This imports the existing `registry.json` into the new SQLite database at `cli_anything/<name>/metadata/registry.db`.

### Step 5: Run tests

```bash
uv run pytest cli_anything/<name>/tests/test_sqlite_registry.py -v
```

All 38 tests should pass. The existing `test_core.py` and `test_full_e2e.py` should also still pass since the module-level API in `registry.py` is backward-compatible.

### Step 6: Verify the CLI still works

```bash
uv run cli-anything-<name> list
uv run cli-anything-<name> search <some-term>
uv run cli-anything-<name> info <some-function>
```

If the CLI imports from `registry.py` module functions, it should work without changes.

## What NOT to change

- **`cli_anything/<name>/<name>_cli.py`** — the existing Click commands stay as-is; the skill adds `proxy` commands and updates the `call` command to wire in proxy support, but existing `list`/`search`/`info`/`categories` commands are untouched
- **`cli_anything/<name>/utils/output.py`** — output formatting is independent of storage
- **`metadata/registry.json`** — keep it as the migration source; it remains the authoritative input

## Proxy Controller

Every harness gets an HTTP proxy controller (`core/proxy.py`) that manages proxy settings for outbound API calls. The proxy is:

- **Persistent** — settings saved to `~/.cache/cli-anything-<name>/proxy.json`
- **Toggleable** — on/off without losing the configured URL
- **CLI-accessible** — `proxy status|set|on|off|toggle|clear` commands
- **Per-call overridable** — `call` command supports `--proxy`/`--no-proxy` flags
- **REPL-integrated** — `proxy` commands work in interactive mode

### proxy.py template

```python
"""
HTTP Proxy controller for <harness-name>.
"""
from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path.home() / ".cache" / "cli-anything-<name>"
_DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_DIR / "proxy.json"


class ProxyController:
    def __init__(self, config_path: Optional[str] = None):
        self._config_path = Path(config_path or _DEFAULT_CONFIG_PATH)
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._url: str = ""
        self._enabled: bool = False
        self._saved_env: dict[str, str] = {}
        self._load()

    @property
    def url(self) -> str:
        return self._url

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def status(self) -> str:
        if not self._url:
            return "No proxy configured"
        state = "ON" if self._enabled else "OFF"
        return f"Proxy [{state}]: {self._url}"

    def set_proxy(self, url: str) -> None:
        self._url = url.strip().rstrip("/")
        self._save()

    def clear_proxy(self) -> None:
        self.disable()
        self._url = ""
        self._save()

    def enable(self) -> None:
        self._enabled = True
        self._apply_env()
        self._save()

    def disable(self) -> None:
        self._enabled = False
        self._restore_env()
        self._save()

    def toggle(self) -> bool:
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    def apply(self) -> None:
        if self._enabled and self._url:
            self._apply_env()

    def _apply_env(self) -> None:
        if not self._url:
            return
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            self._saved_env[key] = os.environ.get(key, "")
            os.environ[key] = self._url
        os.environ["ALL_PROXY"] = self._url

    def _restore_env(self) -> None:
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            if key in self._saved_env:
                if self._saved_env[key]:
                    os.environ[key] = self._saved_env[key]
                else:
                    os.environ.pop(key, None)
        os.environ.pop("ALL_PROXY", None)
        self._saved_env.clear()

    def _save(self) -> None:
        with open(self._config_path, "w") as f:
            json.dump({"url": self._url, "enabled": self._enabled}, f, indent=2)

    def _load(self) -> None:
        if self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    data = json.load(f)
                self._url = data.get("url", "")
                self._enabled = data.get("enabled", False)
                if self._enabled and self._url:
                    self._apply_env()
            except (json.JSONDecodeError, KeyError):
                pass

    def __enter__(self):
        self._was_enabled = self._enabled
        if not self._enabled:
            self.enable()
        return self

    def __exit__(self, *args):
        if not self._was_enabled:
            self.disable()
        return False


_proxy_controller: Optional[ProxyController] = None


def get_proxy(config_path: Optional[str] = None) -> ProxyController:
    global _proxy_controller
    if _proxy_controller is None:
        _proxy_controller = ProxyController(config_path)
    return _proxy_controller
```

### runner.py update

Update `call_<name>_function` to accept an optional `proxy` parameter:

```python
def call_<name>_function(func_name, params=None, proxy=None):
    if params is None:
        params = {}
    if proxy is not None:
        proxy.apply()
    # ... existing function call logic ...
```

### CLI updates

Add to `<name>_cli.py`:

1. Import `get_proxy` from the proxy module
2. Add a `proxy` command group with subcommands: `status`, `set`, `on`, `off`, `toggle`, `clear`
3. Add `--proxy/--no-proxy` options to the `call` command
4. Add proxy commands to the REPL handler
5. Wire `get_proxy()` into the REPL `call` handler so proxy applies automatically when enabled

## Database URL

The `Database` class reads from `<UPPER_NAME>_DATABASE_URL` env var. Defaults to SQLite at `metadata/registry.db`. To switch to PostgreSQL later:

```bash
export <NAME>_DATABASE_URL=postgresql://user:pass@localhost/dbname
```

No code changes needed — SQLAlchemy handles the dialect switch.

## Principles

- **Same schema everywhere.** Every harness gets the same two-table design. This makes cross-harness queries possible and keeps the mental model simple.
- **Backward-compatible.** The module-level functions in `registry.py` keep the same signatures. The CLI, tests, and any other callers don't need to change.
- **Idempotent migration.** `MigrationRunner` upserts by command name. Running it twice produces the same result.
- **Testable.** All code takes a Session via constructor injection. Tests use in-memory SQLite — no filesystem dependency.
