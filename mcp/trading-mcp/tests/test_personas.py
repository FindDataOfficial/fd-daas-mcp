"""Tests for investor persona agents — verify all 5 are creatable and
produce valid outputs.  These tests run without crewai (verify the data
definitions and prompt generation, not live agent execution).
"""

import json
import sys
from pathlib import Path

# Ensure mcp/ is on path so 'from agents.personas import ...' works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def test_persona_defs_count():
    """All 5 famous investor personas are defined."""
    from agents.personas import PERSONA_DEFS
    assert len(PERSONA_DEFS) == 5


def test_persona_defs_structure():
    """Each persona def has all required fields."""
    from agents.personas import PERSONA_DEFS
    required = {"name", "philosophy", "role", "goal", "backstory"}
    for d in PERSONA_DEFS:
        missing = required - set(d.keys())
        assert not missing, f"Persona {d.get('name', '?')} missing: {missing}"
        assert d["goal"]  # non-empty
        assert d["backstory"]  # non-empty
        assert d["name"]  # non-empty


def test_persona_names():
    """The five personas are the expected famous investors."""
    from agents.personas import PERSONA_DEFS
    names = [d["name"] for d in PERSONA_DEFS]
    assert "Warren Buffett" in names
    assert "George Soros" in names
    assert "Peter Lynch" in names
    assert "Ray Dalio" in names
    assert "Jim Simons" in names


def test_persona_prompt():
    """_persona_prompt generates a prompt with ticker and persona name."""
    from agents.personas import _persona_prompt
    prompt = _persona_prompt(0, "AAPL")
    assert "AAPL" in prompt
    assert "Warren Buffett" in prompt
    assert "JSON" in prompt


def test_persona_factory_no_crewai():
    """Factory functions raise ImportError without crewai (expected)."""
    from agents.personas import create_buffett_persona
    try:
        create_buffett_persona()
        # If crewai happens to be installed, agent should be created
        assert True
    except ImportError:
        # Expected — crewai not installed
        pass


def test_schemas_import():
    """All Pydantic schemas are importable."""
    from schemas import (
        PersonaAnalysis,
        MergedReport,
        PipelineResult,
        PortfolioDecision,
        TraderProposal,
        TraderAction,
        PortfolioRating,
    )
    assert PersonaAnalysis
    assert MergedReport
    assert PipelineResult
    assert PortfolioDecision
    assert TraderProposal


def test_persona_analysis_validation():
    """PersonaAnalysis validates correctly."""
    from schemas import PersonaAnalysis, TraderAction
    a = PersonaAnalysis(
        ticker="AAPL",
        investor_name="Warren Buffett",
        action=TraderAction.BUY,
        conviction=8,
        thesis="Strong moat, undervalued",
        key_metrics="ROE 25%, P/E 15",
        risks="Regulatory headwinds",
    )
    assert a.ticker == "AAPL"
    assert a.conviction == 8


def test_persona_analysis_conviction_range():
    """Conviction must be 1-10."""
    from schemas import PersonaAnalysis, TraderAction
    import pydantic

    try:
        PersonaAnalysis(
            ticker="AAPL",
            investor_name="Test",
            action=TraderAction.HOLD,
            conviction=0,  # invalid
            thesis="x",
            key_metrics="x",
            risks="x",
        )
        assert False, "Should have raised validation error"
    except pydantic.ValidationError:
        pass  # expected


def test_merged_report():
    """MergedReport construction works."""
    from schemas import MergedReport, PersonaAnalysis, TraderAction
    a1 = PersonaAnalysis(
        ticker="AAPL", investor_name="Buffett", action=TraderAction.BUY,
        conviction=7, thesis="Good", key_metrics="", risks="",
    )
    a2 = PersonaAnalysis(
        ticker="AAPL", investor_name="Soros", action=TraderAction.BUY,
        conviction=6, thesis="Good too", key_metrics="", risks="",
    )
    report = MergedReport(
        ticker="AAPL",
        consensus_action=TraderAction.BUY,
        consensus_count=2,
        total_personas=2,
        analyses=[a1, a2],
        summary="All agree: BUY",
    )
    assert report.consensus_action == TraderAction.BUY
    assert report.consensus_count == 2


def test_portfolio_decision():
    """PortfolioDecision construction works."""
    from schemas import PortfolioDecision, PortfolioRating
    d = PortfolioDecision(
        ticker="AAPL",
        rating=PortfolioRating.BUY,
        executive_summary="Buy AAPL",
        investment_thesis="Strong growth",
        risk_assessment="Low risk",
    )
    assert d.rating == PortfolioRating.BUY


def test_trader_proposal():
    """TraderProposal construction works."""
    from schemas import TraderProposal, TraderAction
    p = TraderProposal(
        action=TraderAction.BUY,
        reasoning="Upside potential",
        entry_price=150.0,
        stop_loss=135.0,
        position_sizing="5% of portfolio",
    )
    assert p.action == TraderAction.BUY
    assert p.entry_price == 150.0
    assert p.stop_loss == 135.0


def test_pipeline_result():
    """PipelineResult captures partial results."""
    from schemas import PipelineResult
    r = PipelineResult(
        ticker="AAPL",
        analyst_reports={"fundamentals": "Strong"},
        error="LLM not configured",
    )
    assert r.ticker == "AAPL"
    assert r.error == "LLM not configured"
    assert r.analyst_reports["fundamentals"] == "Strong"


def test_analyst_defs():
    """Four analyst types are defined."""
    from agents.analysts import ANALYST_DEFS
    assert len(ANALYST_DEFS) == 4
    keys = [d["key"] for d in ANALYST_DEFS]
    assert keys == ["fundamentals", "sentiment", "news", "market"]


def test_debate_defs():
    """Three debate roles are defined."""
    from agents.debators import DEBATE_DEFS
    assert set(DEBATE_DEFS.keys()) == {"bull", "bear", "manager"}


def test_risk_defs():
    """Four risk management roles are defined."""
    from agents.risk_manager import RISK_DEFS
    assert set(RISK_DEFS.keys()) == {"aggressive", "conservative", "neutral", "pm"}


def test_trader_def():
    """Trader definition has required fields."""
    from agents.trader import TRADER_DEF
    assert "role" in TRADER_DEF
    assert "goal" in TRADER_DEF
    assert "backstory" in TRADER_DEF
