"""composite_tools tests: composite create/list, upstream + tool add/remove,
served-name derivation (<key>_<tool>), and chained-tool add/remove with
`_validate_steps` rejecting malformed steps.

Calls the composite management tools directly. These curate composite config in
the throwaway DB and never spawn an upstream subprocess (only
`list_available_tools` / `make_proxy_tool` / `make_chain_tool` build a live
client, and those are not invoked here). composite-mcp/ is added to sys.path
for the imports.

Convention: composites this module creates are prefixed `zz_test_` and torn
down (with their upstreams/tools/chains) by `_cleanup_composite()` in every test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_COMPOSITE_MCP = Path(__file__).resolve().parents[1] / "src" / "fd_daas_mcp" / "mcp" / "composite"
sys.path.insert(0, str(_COMPOSITE_MCP))
from composite_database import get_composite_db  # noqa: E402
from fd_daas_mcp.models import Composite, CompositeChain, CompositeTool, Upstream  # noqa: E402
import composite_tools  # noqa: E402


def _cleanup_composite() -> None:
    sess = get_composite_db().get_session()
    try:
        ids = [
            c.id for c in sess.query(Composite).filter(Composite.name.like("zz_test_%")).all()
        ]
        if ids:
            sess.query(CompositeChain).filter(
                CompositeChain.composite_id.in_(ids)
            ).delete(synchronize_session=False)
            sess.query(CompositeTool).filter(
                CompositeTool.composite_id.in_(ids)
            ).delete(synchronize_session=False)
            sess.query(Upstream).filter(Upstream.composite_id.in_(ids)).delete(
                synchronize_session=False
            )
            sess.query(Composite).filter(Composite.id.in_(ids)).delete(
                synchronize_session=False
            )
        sess.commit()
    finally:
        sess.close()


def test_composite_create_list_upstream_tool_add_remove():
    _cleanup_composite()
    out = composite_tools.create("zz_test_comp", "d")
    assert "Created composite zz_test_comp" in out

    assert "zz_test_comp" in composite_tools.list()

    up = composite_tools.add_upstream("zz_test_comp", "k1", "stdio", command="echo")
    assert "Added upstream k1 [stdio]" in up
    assert "k1 [stdio]" in composite_tools.list_upstreams("zz_test_comp")

    tool = composite_tools.add_tool("zz_test_comp", "k1", "get_price")
    assert "Served as k1_get_price" in tool
    assert "k1_get_price" in composite_tools.list_tools("zz_test_comp")

    rm_tool = composite_tools.remove_tool("zz_test_comp", "k1", "get_price")
    assert "Removed tool get_price" in rm_tool
    assert "k1_get_price" not in composite_tools.list_tools("zz_test_comp")

    rm_up = composite_tools.remove_upstream("zz_test_comp", "k1")
    assert "Removed upstream k1" in rm_up
    assert "No upstreams" in composite_tools.list_upstreams("zz_test_comp")
    _cleanup_composite()


def test_served_tool_name_is_key_underscore_tool():
    _cleanup_composite()
    composite_tools.create("zz_test_name", "d")
    composite_tools.add_upstream("zz_test_name", "ak", "stdio", command="echo")
    out = composite_tools.add_tool("zz_test_name", "ak", "stock_hist")
    # The served name is derived as <upstream_key>_<tool_name>.
    assert "Served as ak_stock_hist" in out
    listed = composite_tools.list_tools("zz_test_name")
    assert "ak_stock_hist" in listed
    # Sanity: the derivation is strictly key + "_" + tool, not tool + key.
    assert "stock_hist_ak" not in listed
    _cleanup_composite()


def test_chained_tool_add_remove_validates_steps():
    _cleanup_composite()
    composite_tools.create("zz_test_chain", "d")

    # Malformed: control-flow construct rejected by _validate_steps.
    with pytest.raises(ValueError):
        composite_tools.add_chained_tool(
            "zz_test_chain",
            "bad_branch",
            steps=[{"upstream": "k", "tool": "t", "if": True}],
        )
    # Malformed: empty steps.
    with pytest.raises(ValueError):
        composite_tools.add_chained_tool("zz_test_chain", "bad_empty", steps=[])
    # Malformed: step missing 'tool'.
    with pytest.raises(ValueError):
        composite_tools.add_chained_tool(
            "zz_test_chain", "bad_missing", steps=[{"upstream": "k"}]
        )

    # Nothing was persisted for the malformed attempts.
    assert "No chains defined" in composite_tools.list_chained_tools("zz_test_chain")

    # Valid linear pipeline persists and is listed.
    ok = composite_tools.add_chained_tool(
        "zz_test_chain",
        "good",
        steps=[{"upstream": "k", "tool": "t", "input": {"x": 1}}],
        description="a chain",
    )
    assert "Added chain good" in ok
    listed = composite_tools.list_chained_tools("zz_test_chain")
    assert "good" in listed and "1 steps" in listed

    rm = composite_tools.remove_chained_tool("zz_test_chain", "good")
    assert "Removed chain good" in rm
    assert "No chains defined" in composite_tools.list_chained_tools("zz_test_chain")
    _cleanup_composite()
