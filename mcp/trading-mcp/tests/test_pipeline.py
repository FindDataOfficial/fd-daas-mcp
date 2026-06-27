"""Tests for the trading pipeline — verify pipeline stages can be constructed
and that the full pipeline produces structured results (without requiring a live LLM).

These test the pipeline's error handling and schema outputs, not live agent execution.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Clear LLM env BEFORE any server imports (server.py loads dotenv at import time)
_saved_llm_env = {}
for _key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "OPENAI_API_KEY"):
    _val = os.environ.pop(_key, None)
    if _val is not None:
        _saved_llm_env[_key] = _val


def _restore_llm_env():
    for key, val in _saved_llm_env.items():
        os.environ[key] = val


def test_pipeline_returns_result_without_llm():
    """full_pipeline returns PipelineResult with error when no LLM."""
    from server import _run_pipeline
    result = _run_pipeline("AAPL")
    assert result.error is not None
    assert "LLM" in result.error or "crewai" in result.error.lower()
    assert result.ticker == "AAPL"


def test_persona_analysis_returns_merged_report():
    """analyze_ticker returns MergedReport even without LLM."""
    from server import _run_persona_analysis
    from schemas import MergedReport

    result = _run_persona_analysis("AAPL")
    assert isinstance(result, MergedReport)
    assert result.ticker == "AAPL"
    assert result.total_personas == 5
    assert len(result.analyses) == 5
    for a in result.analyses:
        assert a.conviction == 1
        assert "LLM" in a.thesis or "No LLM" in a.thesis


def test_personas_text():
    """list_personas returns text with all 5 investor names."""
    from server import _personas_text
    text = _personas_text()
    assert "Warren Buffett" in text
    assert "George Soros" in text
    assert "Peter Lynch" in text
    assert "Ray Dalio" in text
    assert "Jim Simons" in text
    assert "Value investing" in text
    assert "macro" in text.lower()
    assert "GARP" in text
    assert "risk parity" in text.lower()
    assert "Quantitative" in text


def test_pipeline_result_schema():
    """PipelineResult JSON serialization works."""
    from schemas import PipelineResult, PortfolioDecision, PortfolioRating, TraderProposal, TraderAction

    result = PipelineResult(
        ticker="AAPL",
        analyst_reports={"fundamentals": "Strong report"},
        debate_verdict="BUY with conviction",
        trader_proposal=TraderProposal(
            action=TraderAction.BUY,
            reasoning="Good setup",
            entry_price=150.0,
            stop_loss=140.0,
        ),
        risk_assessments={
            "aggressive": "Go big",
            "conservative": "Be careful",
            "neutral": "Moderate",
        },
        portfolio_decision=PortfolioDecision(
            ticker="AAPL",
            rating=PortfolioRating.BUY,
            executive_summary="Buy",
            investment_thesis="Strong",
            risk_assessment="Low",
        ),
    )

    d = result.model_dump()
    assert d["ticker"] == "AAPL"
    assert d["analyst_reports"]["fundamentals"] == "Strong report"
    assert d["trader_proposal"]["action"] == "Buy"
    assert d["portfolio_decision"]["rating"] == "Buy"

    # Round-trip through JSON
    json_str = json.dumps(d, ensure_ascii=False)
    loaded = json.loads(json_str)
    assert loaded["ticker"] == "AAPL"
