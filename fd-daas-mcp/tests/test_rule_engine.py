"""RuleEngine unit tests: json + script evaluators, disabled rule, missing
script, script without members, ctx.query read-only enforcement, and the
phase-2 deferral of position/llm types.

These tests call RuleEngine.evaluate directly (no registry build), so the
daas-mcp source dir stays on sys.path for the duration of the test session.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

_DAAS_MCP = Path(__file__).resolve().parents[1] / "daas-mcp"
if str(_DAAS_MCP) not in sys.path:
    sys.path.insert(0, str(_DAAS_MCP))

from daas_database import get_database  # noqa: E402
from models import Entity  # noqa: E402
from rule_engine import RuleEngine, RuleContext  # noqa: E402


def _seed() -> None:
    sess = get_database().get_session()
    sess.query(Entity).delete()
    sess.add_all(
        [
            Entity(entity_type="stock", code="600519", name="贵州茅台", exchange="SSE"),
            Entity(entity_type="stock", code="000001", name="平安银行", exchange="SZSE"),
        ]
    )
    sess.commit()


def _json(config: dict) -> SimpleNamespace:
    return SimpleNamespace(
        rule_type="json", target="entity_ids", config_json=config, enabled=True
    )


def _script(path: str) -> SimpleNamespace:
    return SimpleNamespace(
        rule_type="script",
        target="entity_ids",
        config_json={"script_path": path},
        enabled=True,
    )


def test_json_rule_filters_by_exchange():
    _seed()
    sess = get_database().get_session()
    ids = RuleEngine.evaluate(_json({"entity_type": "stock", "exchange": "SSE"}), sess)
    codes = {e.code for e in sess.query(Entity).filter(Entity.id.in_(ids)).all()}
    assert codes == {"600519"}


def test_json_rule_name_regex():
    _seed()
    sess = get_database().get_session()
    ids = RuleEngine.evaluate(_json({"name_regex": "茅台"}), sess)
    assert len(ids) == 1


def test_script_rule_normalizes_codes_to_entity_ids():
    _seed()
    sess = get_database().get_session()
    script = Path(tempfile.mkdtemp()) / "pool.py"
    script.write_text("def members(ctx):\n    return ['600519']\n")
    ids = RuleEngine.evaluate(_script(str(script)), sess, str(sess.bind.url))
    assert len(ids) == 1
    assert sess.get(Entity, ids[0]).code == "600519"


def test_script_rule_skips_unknown_codes():
    _seed()
    sess = get_database().get_session()
    script = Path(tempfile.mkdtemp()) / "pool.py"
    script.write_text("def members(ctx):\n    return ['600519', 'NOPE']\n")
    ids = RuleEngine.evaluate(_script(str(script)), sess, str(sess.bind.url))
    assert len(ids) == 1  # 'NOPE' skipped, not fatal


def test_disabled_rule_returns_empty():
    _seed()
    sess = get_database().get_session()
    rule = SimpleNamespace(
        rule_type="json", target="entity_ids", config_json={"exchange": "SSE"}, enabled=False
    )
    assert RuleEngine.evaluate(rule, sess) == []


def test_missing_script_raises_filenotfound():
    sess = get_database().get_session()
    with pytest.raises(FileNotFoundError):
        RuleEngine.evaluate(_script("/nope/does_not_exist.py"), sess, str(sess.bind.url))


def test_script_without_members_raises_typeerror():
    sess = get_database().get_session()
    script = Path(tempfile.mkdtemp()) / "p.py"
    script.write_text("X = 1\n")
    with pytest.raises(TypeError):
        RuleEngine.evaluate(_script(str(script)), sess, str(sess.bind.url))


def test_ctx_query_is_read_only():
    _seed()
    sess = get_database().get_session()
    ctx = RuleContext(str(sess.bind.url))
    try:
        with pytest.raises(sqlite3.OperationalError):
            ctx.query("DELETE FROM entities WHERE code='600519'")
    finally:
        ctx.close()


def test_position_rule_regex_extracts_codes():
    _seed()
    sess = get_database().get_session()
    rule = SimpleNamespace(
        rule_type="position",
        target="entity_ids",
        config_json={
            "source": {"type": "text", "value": "codes: 600519 and 000001 here"},
            "selector_type": "regex",
            "selector": r"\b(\d{6})\b",
        },
        enabled=True,
    )
    items = RuleEngine.evaluate(rule, sess)
    assert len(items) == 2  # both codes resolve to seeded entities


def test_position_rule_css_extracts_codes():
    _seed()
    sess = get_database().get_session()
    rule = SimpleNamespace(
        rule_type="position",
        target="entity_ids",
        config_json={
            "source": {"type": "text", "value": "<table><tr><td class='c'>600519</td></tr></table>"},
            "selector_type": "css",
            "selector": "td.c",
            "extract": "text",
        },
        enabled=True,
    )
    items = RuleEngine.evaluate(rule, sess)
    assert len(items) == 1
    assert sess.get(Entity, items[0]).code == "600519"


def test_llm_rule_member_mapping(monkeypatch):
    _seed()
    sess = get_database().get_session()
    import process_tools

    monkeypatch.setattr(
        process_tools,
        "extract_text",
        lambda *a, **k: {"records": [{"code": "600519"}], "count": 1},
    )
    rule = SimpleNamespace(
        rule_type="llm",
        target="entity_ids",
        config_json={
            "text": "some news mentioning 600519",
            "schema_json": {},
            "mapping": {"code_from": "code"},
        },
        enabled=True,
    )
    items = RuleEngine.evaluate(rule, sess)
    assert len(items) == 1
    assert sess.get(Entity, items[0]).code == "600519"
