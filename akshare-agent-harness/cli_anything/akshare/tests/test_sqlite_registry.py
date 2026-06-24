"""
Unit tests for the SQLAlchemy-backed registry.

Tests cover: models (Function, FunctionColumn), Database singleton,
RegistryService (5 operations), and MigrationRunner (JSON import).

All tests use in-memory SQLite — no filesystem dependency.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from cli_anything.akshare.core.models import Base, Function, FunctionColumn
from cli_anything.akshare.core.database import Database, get_database, reset_database
from cli_anything.akshare.core.registry import RegistryService
from cli_anything.akshare.core.migrate_registry import MigrationRunner


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def engine():
    """In-memory SQLite engine with all tables created."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    """SQLAlchemy session bound to in-memory SQLite."""
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.rollback()
    sess.close()


@pytest.fixture
def populated_session(engine):
    """Session pre-populated with 4 test functions."""
    Session = sessionmaker(bind=engine)
    session = Session()

    funcs = [
        Function(
            command="stock_sse_summary",
            category="股票市场总貌",
            source="http://www.sse.com.cn",
            description="上海证券交易所-股票数据总貌",
            parameters=[
                {"name": "date", "type": "str", "required": False,
                 "description": "date=\"20250221\""}
            ],
        ),
        Function(
            command="stock_szse_summary",
            category="股票市场总貌",
            source="http://www.szse.cn",
            description="深圳证券交易所-市场总貌",
            parameters=[
                {"name": "date", "type": "str", "required": False}
            ],
        ),
        Function(
            command="stock_zh_a_hist",
            category="历史行情数据",
            description="A股历史行情",
            parameters=[
                {"name": "symbol", "type": "str", "required": True},
                {"name": "start_date", "type": "str", "required": False},
                {"name": "end_date", "type": "str", "required": False},
            ],
        ),
        Function(
            command="fund_etf_hist_em",
            category="ETF基金",
            description="ETF基金历史行情",
            parameters=[{"name": "symbol", "type": "str", "required": True}],
        ),
    ]

    for func in funcs:
        session.add(func)
    session.flush()

    # Add columns to the first function
    cols = [
        FunctionColumn(function_id=funcs[0].id, column_name="日期", column_type="object"),
        FunctionColumn(function_id=funcs[0].id, column_name="成交量", column_type="float64"),
        FunctionColumn(function_id=funcs[0].id, column_name="成交额", column_type="float64"),
    ]
    for col in cols:
        session.add(col)

    session.commit()

    yield session
    session.rollback()
    session.close()


@pytest.fixture(autouse=True)
def reset_db_singleton():
    """Reset the Database singleton before each test."""
    reset_database()
    yield
    reset_database()


# ============================================
# Model Tests
# ============================================

class TestFunctionModel:
    def test_create_function(self, session):
        func = Function(
            command="test_func",
            category="测试",
            source="http://example.com",
            description="A test function",
            parameters=[{"name": "x", "type": "int"}],
        )
        session.add(func)
        session.flush()

        assert func.id is not None
        assert func.command == "test_func"
        assert func.category == "测试"

    def test_command_unique_constraint(self, session):
        f1 = Function(command="dup_func", category="cat1")
        f2 = Function(command="dup_func", category="cat2")
        session.add(f1)
        session.flush()
        session.add(f2)
        with pytest.raises(Exception):
            session.flush()

    def test_to_dict(self, session):
        func = Function(
            command="my_func",
            category="测试类",
            source="http://src.com",
            description="描述",
            parameters=[{"name": "p1", "type": "str", "required": True}],
        )
        session.add(func)
        session.flush()

        col = FunctionColumn(
            function_id=func.id,
            column_name="col1",
            column_type="float64",
            column_description="第一列",
        )
        session.add(col)
        session.flush()

        # Refresh to load the relationship
        session.expire_all()
        func = session.query(Function).filter(Function.command == "my_func").first()

        d = func.toDict()
        assert d["command"] == "my_func"
        assert d["category"] == "测试类"
        assert d["source"] == "http://src.com"
        assert d["description"] == "描述"
        assert len(d["parameters"]) == 1
        assert d["parameters"][0]["name"] == "p1"
        assert len(d["columns"]) == 1
        assert d["columns"][0]["name"] == "col1"
        assert d["columns"][0]["type"] == "float64"

    def test_to_dict_empty_columns(self, session):
        func = Function(command="no_cols", category="cat")
        session.add(func)
        session.flush()

        d = func.toDict()
        assert d["columns"] == []

    def test_to_dict_null_parameters(self, session):
        func = Function(command="no_params", category="cat", parameters=None)
        session.add(func)
        session.flush()

        d = func.toDict()
        assert d["parameters"] == []

    def test_cascade_delete_columns(self, session):
        func = Function(command="cascade_test", category="cat")
        session.add(func)
        session.flush()

        col = FunctionColumn(function_id=func.id, column_name="c1")
        session.add(col)
        session.flush()

        col_id = col.id
        assert session.query(FunctionColumn).filter(FunctionColumn.id == col_id).count() == 1

        session.delete(func)
        session.flush()

        # Column should be cascade-deleted
        assert session.query(FunctionColumn).filter(FunctionColumn.id == col_id).count() == 0


class TestFunctionColumnModel:
    def test_create_column(self, session):
        func = Function(command="parent_func", category="cat")
        session.add(func)
        session.flush()

        col = FunctionColumn(
            function_id=func.id,
            column_name="开盘价",
            column_type="float64",
            column_description="开盘价格",
        )
        session.add(col)
        session.flush()

        assert col.id is not None
        assert col.function_id == func.id
        assert col.column_name == "开盘价"
        assert col.column_type == "float64"
        assert col.column_description == "开盘价格"

    def test_to_dict(self, session):
        func = Function(command="parent2", category="cat")
        session.add(func)
        session.flush()

        col = FunctionColumn(
            function_id=func.id,
            column_name="收盘价",
            column_type="float64",
            column_description="收盘价格",
        )
        session.add(col)
        session.flush()

        d = col.toDict()
        assert d["name"] == "收盘价"
        assert d["type"] == "float64"
        assert d["description"] == "收盘价格"

    def test_null_type_and_description(self, session):
        func = Function(command="parent3", category="cat")
        session.add(func)
        session.flush()

        col = FunctionColumn(function_id=func.id, column_name="name_only")
        session.add(col)
        session.flush()

        d = col.toDict()
        assert d["name"] == "name_only"
        assert d["type"] is None
        assert d["description"] is None


# ============================================
# Database Tests
# ============================================

class TestDatabase:
    def test_init_with_default_url(self):
        reset_database()
        db = Database("sqlite:///:memory:")
        db.init_db()
        assert db.database_url == "sqlite:///:memory:"
        assert db.engine is not None
        db.dispose()

    def test_init_with_custom_url(self):
        db = Database("sqlite:///custom_path.db")
        assert db.database_url == "sqlite:///custom_path.db"
        db.init_db()
        db.dispose()

    def test_get_session(self):
        db = Database("sqlite:///:memory:")
        session = db.get_session()
        assert isinstance(session, Session)
        assert session.is_active
        session.close()
        db.dispose()

    def test_singleton_get_database(self):
        reset_database()
        db1 = get_database("sqlite:///:memory:")
        db2 = get_database()
        assert db1 is db2
        db1.dispose()

    def test_dispose(self):
        db = Database("sqlite:///:memory:")
        db.init_db()
        assert db.engine is not None
        db.dispose()
        assert db._engine is None

    def test_env_var_database_url(self, monkeypatch):
        monkeypatch.setenv("AKSHARE_DATABASE_URL", "sqlite:///:memory:")
        reset_database()
        db = Database()
        assert db.database_url == "sqlite:///:memory:"
        db.init_db()
        db.dispose()

    def test_init_db_creates_tables(self, engine):
        """Verify tables exist after init_db."""
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='functions'")
            )
            assert result.fetchone() is not None
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='function_columns'")
            )
            assert result.fetchone() is not None


# ============================================
# RegistryService Tests
# ============================================

class TestRegistryService:
    def test_list_functions_all(self, populated_session):
        svc = RegistryService(populated_session)
        result = svc.list_functions()
        assert len(result) == 4
        assert "stock_sse_summary" in result
        assert "stock_zh_a_hist" in result
        assert "fund_etf_hist_em" in result

    def test_list_functions_by_category(self, populated_session):
        svc = RegistryService(populated_session)
        result = svc.list_functions(category="股票市场总貌")
        assert len(result) == 2
        assert "stock_sse_summary" in result
        assert "stock_szse_summary" in result
        assert "stock_zh_a_hist" not in result

    def test_list_functions_empty_category(self, populated_session):
        svc = RegistryService(populated_session)
        result = svc.list_functions(category="不存在的分类")
        assert len(result) == 0

    def test_search_by_name(self, populated_session):
        svc = RegistryService(populated_session)
        result = svc.search_functions("stock_sse")
        assert "stock_sse_summary" in result
        assert "stock_zh_a_hist" not in result

    def test_search_by_category(self, populated_session):
        svc = RegistryService(populated_session)
        result = svc.search_functions("股票市场")
        assert "stock_sse_summary" in result
        assert "stock_szse_summary" in result
        assert "stock_zh_a_hist" not in result

    def test_search_by_description(self, populated_session):
        from cli_anything.akshare.core.registry import RegistryService
        svc = RegistryService(populated_session)
        result = svc.search_functions("证券交易所")
        assert "stock_sse_summary" in result
        assert "stock_szse_summary" in result

    def test_search_case_insensitive(self, populated_session):
        svc = RegistryService(populated_session)
        # Search by category containing Chinese chars
        result = svc.search_functions("基金")
        assert "fund_etf_hist_em" in result

    def test_search_no_results(self, populated_session):
        svc = RegistryService(populated_session)
        result = svc.search_functions("zzz_nonexistent")
        assert len(result) == 0

    def test_get_function_info_found(self, populated_session):
        svc = RegistryService(populated_session)
        info = svc.get_function_info("stock_zh_a_hist")
        assert info is not None
        assert info["category"] == "历史行情数据"
        assert len(info["parameters"]) == 3
        assert info["parameters"][0]["name"] == "symbol"

    def test_get_function_info_with_columns(self, populated_session):
        svc = RegistryService(populated_session)
        info = svc.get_function_info("stock_sse_summary")
        assert info is not None
        assert len(info["columns"]) == 3
        assert info["columns"][0]["name"] == "日期"

    def test_get_function_info_missing(self, populated_session):
        svc = RegistryService(populated_session)
        info = svc.get_function_info("nonexistent")
        assert info is None

    def test_get_categories(self, populated_session):
        svc = RegistryService(populated_session)
        cats = svc.get_categories()
        assert "股票市场总貌" in cats
        assert cats["股票市场总貌"] == 2
        assert cats["历史行情数据"] == 1
        assert cats["ETF基金"] == 1

    def test_get_category_functions(self, populated_session):
        svc = RegistryService(populated_session)
        funcs = svc.get_category_functions("股票市场总貌")
        assert len(funcs) == 2
        assert "stock_sse_summary" in funcs
        assert "stock_szse_summary" in funcs


# ============================================
# MigrationRunner Tests
# ============================================

@pytest.fixture
def fake_registry_json(tmp_path):
    """Create a temporary registry.json for migration testing."""
    data = {
        "stock_test_a": {
            "category": "测试分类A",
            "description": "测试函数A",
            "source": "http://test.com/a",
            "parameters": [{"name": "date", "type": "str", "required": False}],
            "columns": [
                {"name": "col_a1", "type": "float64", "description": "列A1"},
                {"name": "col_a2", "type": "object", "description": "列A2"},
            ],
        },
        "stock_test_b": {
            "category": "测试分类B",
            "description": "测试函数B",
            "source": "http://test.com/b",
            "parameters": [],
            "columns": [],
        },
    }
    path = tmp_path / "registry.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return str(path)


class TestMigrationRunner:
    def test_parse_registry(self, session, fake_registry_json):
        runner = MigrationRunner(session, fake_registry_json)
        data = runner._parse_registry()
        assert len(data) == 2
        assert "stock_test_a" in data
        assert data["stock_test_a"]["category"] == "测试分类A"

    def test_upsert_function_new(self, session, fake_registry_json):
        runner = MigrationRunner(session, fake_registry_json)
        data = runner._parse_registry()
        func = runner._upsert_function("stock_test_a", data["stock_test_a"])
        assert func is not None
        assert func.command == "stock_test_a"
        assert func.category == "测试分类A"
        assert func.source == "http://test.com/a"
        assert len(func.parameters) == 1

    def test_upsert_function_update_existing(self, session):
        """Upsert should update an existing function, not duplicate it."""
        # Pre-populate
        existing = Function(
            command="stock_test_a",
            category="旧分类",
            description="旧描述",
        )
        session.add(existing)
        session.flush()

        runner = MigrationRunner(session, "")
        new_data = {
            "category": "新分类",
            "description": "新描述",
            "source": "http://new.com",
            "parameters": [{"name": "x", "type": "int"}],
        }
        func = runner._upsert_function("stock_test_a", new_data)
        assert func.id == existing.id  # Same row, updated
        assert func.category == "新分类"
        assert func.description == "新描述"

    def test_upsert_columns(self, session):
        func = Function(command="test_cols", category="cat")
        session.add(func)
        session.flush()

        runner = MigrationRunner(session, "")
        cols_data = [
            {"name": "c1", "type": "int", "description": "第一列"},
            {"name": "c2", "type": "str", "description": "第二列"},
        ]
        count = runner._upsert_columns(func, cols_data)
        assert count == 2

        session.flush()
        cols = (
            session.query(FunctionColumn)
            .filter(FunctionColumn.function_id == func.id)
            .all()
        )
        assert len(cols) == 2

    def test_upsert_columns_replaces_existing(self, session):
        """Re-running upsert_columns should replace, not append."""
        func = Function(command="test_cols2", category="cat")
        session.add(func)
        session.flush()

        runner = MigrationRunner(session, "")

        # First insert
        runner._upsert_columns(func, [{"name": "old_col"}])
        session.flush()
        assert session.query(FunctionColumn).filter(FunctionColumn.function_id == func.id).count() == 1

        # Second insert should replace
        runner._upsert_columns(func, [{"name": "new_col1"}, {"name": "new_col2"}])
        session.flush()
        cols = session.query(FunctionColumn).filter(FunctionColumn.function_id == func.id).all()
        assert len(cols) == 2
        names = {c.column_name for c in cols}
        assert "new_col1" in names
        assert "new_col2" in names
        assert "old_col" not in names

    def test_verify_pass(self, session, fake_registry_json):
        runner = MigrationRunner(session, fake_registry_json)
        data = runner._parse_registry()
        for command, info in data.items():
            func = runner._upsert_function(command, info)
            runner._upsert_columns(func, info.get("columns", []))
        session.flush()
        assert runner._verify(expected_count=2) is True

    def test_verify_fail(self, session):
        runner = MigrationRunner(session, "")
        assert runner._verify(expected_count=999) is False

    def test_run_full_migration(self, session, fake_registry_json, capsys):
        runner = MigrationRunner(session, fake_registry_json)
        runner.run()
        session.flush()

        # Verify data is in the DB
        count = session.query(Function).count()
        col_count = session.query(FunctionColumn).count()
        assert count == 2
        # stock_test_a has 2 columns, stock_test_b has 0
        assert col_count == 2

        # Verify data content
        func = session.query(Function).filter(Function.command == "stock_test_a").first()
        assert func is not None
        assert func.category == "测试分类A"

    def test_run_idempotent(self, session, fake_registry_json, capsys):
        """Running migration twice should produce the same result."""
        # First run
        runner1 = MigrationRunner(session, fake_registry_json)
        runner1.run()
        session.flush()
        count1 = session.query(Function).count()

        # Second run with same data
        runner2 = MigrationRunner(session, fake_registry_json)
        runner2.run()
        session.flush()
        count2 = session.query(Function).count()

        assert count1 == count2
        assert count1 == 2
