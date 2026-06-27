"""Pydantic schemas for trading-mcp structured outputs."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# Shared enums
# ═══════════════════════════════════════════════════════════════


class PortfolioRating(str, Enum):
    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


class TraderAction(str, Enum):
    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


# ═══════════════════════════════════════════════════════════════
# Persona output
# ═══════════════════════════════════════════════════════════════


class PersonaAnalysis(BaseModel):
    """Output from a single investor persona agent."""

    ticker: str = Field(description="Stock ticker analyzed")
    investor_name: str = Field(description="Name of the investor persona (e.g. Warren Buffett)")
    action: TraderAction = Field(description="Recommended action: Buy, Hold, or Sell")
    conviction: int = Field(
        ge=1, le=10, description="Conviction level: 1 (uncertain) to 10 (very confident)"
    )
    thesis: str = Field(description="Core investment thesis in the persona's voice")
    key_metrics: str = Field(description="Key metrics or data points supporting the thesis")
    risks: str = Field(description="Key risks identified")


class MergedReport(BaseModel):
    """Consensus report from all five personas."""

    ticker: str
    consensus_action: TraderAction
    consensus_count: int = Field(description="Number of personas agreeing with consensus")
    total_personas: int = Field(default=5)
    analyses: list[PersonaAnalysis]
    summary: str = Field(description="Synthesized summary of all perspectives")


# ═══════════════════════════════════════════════════════════════
# Pipeline outputs
# ═══════════════════════════════════════════════════════════════


class TraderProposal(BaseModel):
    """Output from the Trader agent."""

    action: TraderAction
    reasoning: str = Field(description="Why this action")
    entry_price: Optional[float] = Field(default=None, description="Suggested entry price if buying")
    stop_loss: Optional[float] = Field(default=None, description="Stop loss level if buying")
    position_sizing: Optional[str] = Field(default=None, description="Position sizing guidance")


class PortfolioDecision(BaseModel):
    """Final decision from the Portfolio Manager after risk debate."""

    ticker: str
    rating: PortfolioRating
    executive_summary: str = Field(description="One-paragraph summary of the decision")
    investment_thesis: str = Field(description="Full investment thesis with supporting evidence")
    risk_assessment: str = Field(description="Key risks and mitigation considerations")


class PipelineResult(BaseModel):
    """Full output of the end-to-end trading pipeline."""

    ticker: str
    analyst_reports: dict[str, str] = Field(
        default_factory=dict,
        description="Reports from fundamentals, sentiment, news, market analysts",
    )
    debate_verdict: str = Field(default="", description="Bull-bear debate conclusion")
    trader_proposal: Optional[TraderProposal] = None
    risk_assessments: dict[str, str] = Field(
        default_factory=dict,
        description="Assessments from aggressive, conservative, neutral risk analysts",
    )
    portfolio_decision: Optional[PortfolioDecision] = None
    error: Optional[str] = Field(default=None, description="Error message if pipeline failed")
