"""Tests for the trading-mcp server — verify tools are callable and
the registry registration logic works.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_server_imports():
    """Server module can be imported without errors."""
    from server import app
    assert app.name == "trading-mcp"


def test_trading_tools_defined():
    """All 5 trading tools are defined in TRADING_TOOLS."""
    from server import TRADING_TOOLS
    commands = {t["command"] for t in TRADING_TOOLS}
    assert commands == {
        "list_personas",
        "analyze_ticker",
        "bull_bear_debate",
        "risk_debate",
        "full_pipeline",
    }


def test_trading_tools_have_descriptions():
    """Each tool has a description."""
    from server import TRADING_TOOLS
    for t in TRADING_TOOLS:
        assert t["description"], f"Tool {t['command']} missing description"
        assert t["category"], f"Tool {t['command']} missing category"


def test_list_personas_tool():
    """list_personas tool returns valid output."""
    from server import _personas_text
    result = _personas_text()
    assert "Famous Investor Personas" in result
    assert "Warren Buffett" in result
    assert "Jim Simons" in result


def test_analyze_ticker_tool():
    """analyze_ticker returns valid JSON with merged report."""
    import os

    # Clear LLM env to avoid API calls
    saved = {}
    for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "OPENAI_API_KEY"):
        val = os.environ.pop(key, None)
        if val is not None:
            saved[key] = val

    try:
        from server import _run_persona_analysis
        result = _run_persona_analysis("000001")
        d = result.model_dump()
        assert d["ticker"] == "000001"
        assert d["total_personas"] == 5
        assert len(d["analyses"]) == 5
        assert d["consensus_action"] in ("Buy", "Hold", "Sell")
    finally:
        for key, val in saved.items():
            os.environ[key] = val


def test_register_in_registry():
    """_register_in_registry runs without error."""
    from server import _register_in_registry
    msg = _register_in_registry()
    assert "trading-mcp" in msg
    assert "registered" in msg or "skipped" in msg


def test_tool_parameters_well_formed():
    """All tools have well-formed parameter definitions."""
    from server import TRADING_TOOLS
    for t in TRADING_TOOLS:
        for p in t.get("parameters", []):
            assert "name" in p
            assert "type" in p
            assert "required" in p
            assert "description" in p
