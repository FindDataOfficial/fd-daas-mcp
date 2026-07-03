"""Tests for datasource management, column provenance, and snapshot tools."""
import os
import sys
import pytest

from sqlalchemy import text

# Ensure leader-mcp is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leader_database import get_leader_db, reset_leader_db
from models import Function, FunctionColumn, DataSnapshot, Base


@pytest.fixture(autouse=True)
def clean_db():
    """Use a fresh in-memory database for each test."""
    db_url = os.environ.get("LEADER_MCP_DATABASE_URL")
    # leader_database reads DAAS_DATABASE_URL, not LEADER_MCP_DATABASE_URL.
    os.environ["DAAS_DATABASE_URL"] = "sqlite:///:memory:"
    reset_leader_db()
    yield
    reset_leader_db()
    if db_url is not None:
        os.environ["LEADER_MCP_DATABASE_URL"] = db_url
    else:
        os.environ.pop("DAAS_DATABASE_URL", None)


def _seed_function(session, harness="akshare", command="test_func", category="test"):
    func = Function(harness=harness, command=command, category=category)
    session.add(func)
    session.flush()
    for col_data in [
        {"name": "日期", "type": "object", "description": "trade date"},
        {"name": "收盘", "type": "float64", "description": "close price"},
        {"name": "成交量", "type": "int64", "description": "volume"},
    ]:
        col = FunctionColumn(
            function_id=func.id,
            column_name=col_data["name"],
            column_type=col_data["type"],
            column_description=col_data["description"],
        )
        session.add(col)
    session.commit()
    return func


class TestSchemaMigration:
    """Task 6.1"""

    def test_new_columns_exist(self, clean_db):
        db = get_leader_db()
        db.init_db()
        session = db.get_session()
        try:
            result = session.execute(text("PRAGMA table_info(functions)")).fetchall()
            cols = [r[1] for r in result]
            assert "is_datasource" in cols
            assert "enabled" in cols
            assert "last_fetched_at" in cols

            result = session.execute(text("PRAGMA table_info(function_columns)")).fetchall()
            cols = [r[1] for r in result]
            assert "source_field" in cols
            assert "unit" in cols
            assert "semantic_type" in cols

            tables = [
                r[0]
                for r in session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
            ]
            assert "data_snapshots" in tables
        finally:
            session.close()

    def test_new_columns_default_values(self, clean_db):
        db = get_leader_db()
        db.init_db()
        session = db.get_session()
        try:
            func = _seed_function(session)
            assert func.is_datasource == False
            assert func.enabled == True
            assert func.last_fetched_at is None

            col = func.columns[0]
            assert col.source_field is None
            assert col.unit is None
            assert col.semantic_type is None
        finally:
            session.close()


class TestDatasourceTools:
    """Task 6.2"""

    def test_list_datasources_empty(self, clean_db):
        from leader_tools import list_datasources

        db = get_leader_db()
        session = db.get_session()
        try:
            _seed_function(session)
        finally:
            session.close()

        result = list_datasources()
        assert "No datasources configured" in result

    def test_list_datasources_with_data(self, clean_db):
        from leader_tools import list_datasources, toggle_datasource

        db = get_leader_db()
        session = db.get_session()
        try:
            _seed_function(session)
        finally:
            session.close()

        toggle_datasource("akshare", "test_func", is_datasource=True, enabled=True)
        result = list_datasources()
        assert "test_func" in result
        assert "[✓]" in result

    def test_list_datasources_disabled(self, clean_db):
        from leader_tools import list_datasources, toggle_datasource

        db = get_leader_db()
        session = db.get_session()
        try:
            _seed_function(session)
        finally:
            session.close()

        toggle_datasource("akshare", "test_func", is_datasource=True, enabled=False)
        result = list_datasources()
        assert "test_func" in result
        assert "[✗]" in result

    def test_toggle_datasource_not_found(self, clean_db):
        from leader_tools import toggle_datasource

        db = get_leader_db()
        db.init_db()
        result = toggle_datasource("akshare", "nonexistent", is_datasource=True)
        assert "not found" in result

    def test_toggle_datasource_unmark(self, clean_db):
        from leader_tools import toggle_datasource, list_datasources

        db = get_leader_db()
        session = db.get_session()
        try:
            _seed_function(session)
        finally:
            session.close()

        toggle_datasource("akshare", "test_func", is_datasource=True)
        result = list_datasources()
        assert "test_func" in result

        toggle_datasource("akshare", "test_func", is_datasource=False)
        result = list_datasources()
        assert "No datasources configured" in result


class TestColumnProvenanceTools:
    """Task 6.3"""

    def test_get_provenance_defaults(self, clean_db):
        from leader_tools import get_column_provenance

        db = get_leader_db()
        session = db.get_session()
        try:
            _seed_function(session)
        finally:
            session.close()

        result = get_column_provenance("akshare", "test_func")
        assert "日期" in result
        assert "收盘" in result
        assert "成交量" in result

    def test_get_provenance_not_found(self, clean_db):
        from leader_tools import get_column_provenance

        db = get_leader_db()
        db.init_db()
        result = get_column_provenance("akshare", "nonexistent")
        assert "not found" in result

    def test_update_column_meta_partial(self, clean_db):
        from leader_tools import update_column_meta, get_column_provenance

        db = get_leader_db()
        session = db.get_session()
        try:
            _seed_function(session)
        finally:
            session.close()

        # Update only unit
        result = update_column_meta(
            "akshare", "test_func", "收盘", unit="CNY"
        )
        assert "unit=CNY" in result

        # Verify
        provenance = get_column_provenance("akshare", "test_func")
        assert "CNY" in provenance

    def test_update_column_meta_all_fields(self, clean_db):
        from leader_tools import update_column_meta, get_column_provenance

        db = get_leader_db()
        session = db.get_session()
        try:
            _seed_function(session)
        finally:
            session.close()

        result = update_column_meta(
            "akshare", "test_func", "日期",
            source_field="trade_date", unit="", semantic_type="date"
        )
        assert "source_field=trade_date" in result
        assert "semantic_type=date" in result

    def test_update_column_not_found(self, clean_db):
        from leader_tools import update_column_meta

        db = get_leader_db()
        session = db.get_session()
        try:
            _seed_function(session)
        finally:
            session.close()

        result = update_column_meta(
            "akshare", "test_func", "nonexistent", unit="CNY"
        )
        assert "not found" in result


class TestSnapshotTools:
    """Task 6.4"""

    def test_list_snapshots_empty(self, clean_db):
        from leader_tools import list_snapshots

        db = get_leader_db()
        db.init_db()
        result = list_snapshots()
        assert "No snapshots" in result

    def test_query_snapshot_not_found(self, clean_db):
        from leader_tools import query_snapshots

        db = get_leader_db()
        db.init_db()
        result = query_snapshots(99999)
        assert "not found" in result
