"""Tests for DAAS registry service."""
import pytest
import tempfile
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cli_anything.daas.core.models import Base, Source, Function, FunctionColumn
from cli_anything.daas.core.registry import RegistryService


@pytest.fixture
def registry():
    """Create an in-memory registry for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    svc = RegistryService(session)

    # Seed test data
    svc.upsert_source({
        "name": "test_src",
        "label": "Test Source",
        "description": "A test data source",
    })

    svc.upsert_function("test_src", {
        "name": "test_src_func1",
        "label": "Test Function 1",
        "description": "Returns test data",
        "category": "test_cat",
        "parameters": [{"name": "x", "type": "int", "required": True}],
        "columns": [
            {"name": "col_a", "type": "str", "description": "Column A"},
            {"name": "col_b", "type": "float64", "description": "Column B"},
        ],
    })

    svc.upsert_function("test_src", {
        "name": "test_src_func2",
        "label": "Test Function 2",
        "description": "Another test",
        "category": "other_cat",
        "parameters": [],
        "columns": [],
    })

    session.commit()
    yield svc
    session.close()


def test_list_functions(registry):
    funcs = registry.list_functions()
    assert len(funcs) == 2


def test_list_functions_by_source(registry):
    funcs = registry.list_functions(source="test_src")
    assert len(funcs) == 2


def test_search_functions(registry):
    results = registry.search_functions("test")
    assert len(results) == 2
    results = registry.search_functions("func1")
    assert len(results) == 1
    assert results[0]["name"] == "test_src_func1"


def test_get_function_info(registry):
    info = registry.get_function_info("test_src_func1")
    assert info is not None
    assert info["name"] == "test_src_func1"
    assert info["category"] == "test_cat"
    assert len(info["columns"]) == 2


def test_get_function_info_not_found(registry):
    info = registry.get_function_info("nonexistent")
    assert info is None


def test_get_categories(registry):
    cats = registry.get_categories()
    assert len(cats) == 2  # test_cat, other_cat


def test_list_sources(registry):
    sources = registry.list_sources()
    assert len(sources) == 1
    assert sources[0]["name"] == "test_src"
    assert sources[0]["function_count"] == 2


def test_upsert_idempotent(registry):
    """Upserting the same function twice should not duplicate."""
    registry.upsert_function("test_src", {
        "name": "test_src_func1",
        "label": "Updated Label",
        "description": "Updated desc",
        "category": "test_cat",
        "parameters": [],
        "columns": [{"name": "new_col", "type": "int", "description": ""}],
    })
    registry._session.commit()

    funcs = registry.list_functions(source="test_src")
    assert len(funcs) == 2  # Still 2, no duplicate
    info = registry.get_function_info("test_src_func1")
    assert info["label"] == "Updated Label"
    assert len(info["columns"]) == 1  # Columns replaced
