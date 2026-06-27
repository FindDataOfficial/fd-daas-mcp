"""
MCP Server for Trading Analysis — famous investor personas + TradingAgents pipeline.

Exposes tools that Claude Code can invoke directly:
  list_personas     — list available investor personas with philosophies
  analyze_ticker    — 5 personas analyze a stock, merge into consensus report
  bull_bear_debate  — bull vs bear debate with research manager verdict
  risk_debate       — aggressive/conservative/neutral risk debate with PM decision
  full_pipeline     — end-to-end: analysts → debate → trader → risk → decision

Usage:
    python server.py          # stdio transport (default for Claude Code)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent  # project root
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

from fastmcp import FastMCP

from schemas import (
    MergedReport,
    PersonaAnalysis,
    PipelineResult,
    PortfolioDecision,
    PortfolioRating,
    TraderAction,
    TraderProposal,
)

app = FastMCP(name="trading-mcp")


# ═══════════════════════════════════════════════════════════════
# LLM helper
# ═══════════════════════════════════════════════════════════════

def _get_llm():
    """Get an LLM for CrewAI agents.  Reads LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
    from the shared root .env.  Returns None if no credentials are configured."""
    try:
        from crewai import LLM

        api_key = os.environ.get("LLM_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return None

        base_url = os.environ.get("LLM_BASE_URL", "")
        model = os.environ.get("LLM_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o"))

        kwargs = {"model": model, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        return LLM(**kwargs)
    except Exception:
        return None


def _crewai_available() -> bool:
    try:
        import crewai  # noqa: F401
        return True
    except ImportError:
        return False


# ═══════════════════════════════════════════════════════════════
# Registry self-registration (idempotent upsert into daas.db)
# ═══════════════════════════════════════════════════════════════

TRADING_TOOLS = [
    {
        "command": "list_personas",
        "category": "trading/personas",
        "description": "List available famous investor personas and their investment philosophies",
        "parameters": [],
    },
    {
        "command": "analyze_ticker",
        "category": "trading/personas",
        "description": "Five famous investor personas analyze a stock ticker and produce a consensus report",
        "parameters": [
            {"name": "ticker", "type": "str", "required": True, "description": "Stock ticker symbol (e.g. AAPL, 000001)"},
        ],
    },
    {
        "command": "bull_bear_debate",
        "category": "trading/pipeline",
        "description": "Bull vs bear researcher debate with research manager verdict",
        "parameters": [
            {"name": "ticker", "type": "str", "required": True, "description": "Stock ticker symbol"},
            {"name": "thesis", "type": "str", "required": False, "description": "Optional starting thesis to debate"},
        ],
    },
    {
        "command": "risk_debate",
        "category": "trading/pipeline",
        "description": "Aggressive/conservative/neutral risk debate with portfolio manager final decision",
        "parameters": [
            {"name": "ticker", "type": "str", "required": True, "description": "Stock ticker symbol"},
            {"name": "proposal_json", "type": "str", "required": False, "description": "Trader proposal as JSON string"},
        ],
    },
    {
        "command": "full_pipeline",
        "category": "trading/pipeline",
        "description": "End-to-end TradingAgents pipeline: analysts → debate → trader → risk → decision",
        "parameters": [
            {"name": "ticker", "type": "str", "required": True, "description": "Stock ticker symbol"},
        ],
    },
]


def _register_in_registry() -> str:
    """Idempotent upsert of trading tools into the unified functions table."""
    try:
        # Add mcp/ to path so 'from models import ...' works
        _ensure_mcp_on_path()

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models import Base, Function

        db_url = os.environ.get("DAAS_DATABASE_URL")
        if not db_url:
            db_path = ROOT / "daas.db"
            db_url = f"sqlite:///{db_path}"

        engine = create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
        )
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        try:
            upserted = 0
            for tool in TRADING_TOOLS:
                func = (
                    session.query(Function)
                    .filter(Function.harness == "trading", Function.command == tool["command"])
                    .first()
                )
                if func is None:
                    func = Function(harness="trading", command=tool["command"])

                func.category = tool["category"]
                func.description = tool["description"]
                func.parameters = tool["parameters"]
                func.source = "trading-mcp"
                session.add(func)
                upserted += 1

            session.commit()
            return f"trading-mcp: {upserted} tools registered in daas.db"
        finally:
            session.close()
    except Exception as e:
        return f"trading-mcp registry registration skipped: {e}"


def _ensure_mcp_on_path():
    """Ensure mcp/ is on sys.path so 'from models import ...' works."""
    mcp_dir = str(ROOT)
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)


# ═══════════════════════════════════════════════════════════════
# Persona helpers
# ═══════════════════════════════════════════════════════════════

def _personas_text() -> str:
    """Static text listing all personas — no LLM needed."""
    from agents.personas import PERSONA_DEFS

    lines = ["## Famous Investor Personas", ""]
    for i, d in enumerate(PERSONA_DEFS, 1):
        lines.append(f"**{i}. {d['name']}**")
        lines.append(f"   {d['philosophy']}")
        lines.append("")
    return "\n".join(lines)


def _run_persona_analysis(ticker: str) -> dict:
    """Run all 5 personas on a ticker.  Falls back to prompt-only if no LLM."""
    from agents.personas import PERSONA_DEFS, _persona_prompt
    from agents.personas import (
        create_buffett_persona,
        create_soros_persona,
        create_lynch_persona,
        create_dalio_persona,
        create_simons_persona,
    )

    factories = [
        create_buffett_persona,
        create_soros_persona,
        create_lynch_persona,
        create_dalio_persona,
        create_simons_persona,
    ]

    llm = _get_llm()

    analyses = []
    for i, d in enumerate(PERSONA_DEFS):
        name = d["name"]
        philosophy = d["philosophy"]
        try:
            prompt = _persona_prompt(i, ticker)

            if llm is not None and _crewai_available():
                from crewai import Task, Crew
                agent = factories[i](llm=llm)
                task = Task(
                    description=prompt,
                    expected_output="JSON analysis",
                    agent=agent,
                )
                crew = Crew(agents=[agent], tasks=[task], verbose=False)
                result = crew.kickoff()
                result_str = str(result) if result else "{}"
                analysis = _parse_analysis_json(result_str, ticker, name)
            else:
                analysis = _fallback_analysis(ticker, name, philosophy)

            analyses.append(analysis)
        except Exception as e:
            analyses.append(PersonaAnalysis(
                ticker=ticker,
                investor_name=name,
                action=TraderAction.HOLD,
                conviction=1,
                thesis=f"Analysis unavailable: {e}",
                key_metrics="N/A",
                risks="Error during analysis",
            ))

    # Merge into consensus
    return _merge_analyses(ticker, analyses)


def _parse_analysis_json(raw: str, ticker: str, name: str) -> PersonaAnalysis:
    """Try to extract JSON from a potentially messy agent response."""
    import re

    # Find JSON block
    match = re.search(r'\{[^{}]*"ticker"[^{}]*\}', raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return PersonaAnalysis(
                ticker=data.get("ticker", ticker),
                investor_name=data.get("investor_name", name),
                action=TraderAction(data.get("action", "Hold")),
                conviction=max(1, min(10, int(data.get("conviction", 5)))),
                thesis=data.get("thesis", raw[:500]),
                key_metrics=data.get("key_metrics", ""),
                risks=data.get("risks", ""),
            )
        except (json.JSONDecodeError, ValueError):
            pass

    return PersonaAnalysis(
        ticker=ticker,
        investor_name=name,
        action=TraderAction.HOLD,
        conviction=5,
        thesis=raw[:500] if raw else "No analysis produced",
        key_metrics="",
        risks="",
    )


def _fallback_analysis(ticker: str, name: str, philosophy: str) -> PersonaAnalysis:
    """Return a placeholder analysis when no LLM is available."""
    return PersonaAnalysis(
        ticker=ticker,
        investor_name=name,
        action=TraderAction.HOLD,
        conviction=1,
        thesis=f"[No LLM configured] Would evaluate {ticker} through: {philosophy}. "
               f"Set OPENAI_API_KEY or configure TRADING_MCP_MODEL to enable live analysis.",
        key_metrics="LLM not available",
        risks="LLM not available",
    )


def _merge_analyses(ticker: str, analyses: list[PersonaAnalysis]) -> MergedReport:
    """Merge persona analyses into a consensus report."""
    from collections import Counter

    actions = [a.action for a in analyses]
    counts = Counter(actions)
    consensus = counts.most_common(1)[0][0]
    consensus_count = counts[consensus]

    buy_count = counts.get(TraderAction.BUY, 0)
    sell_count = counts.get(TraderAction.SELL, 0)
    hold_count = counts.get(TraderAction.HOLD, 0)

    summary = (
        f"Consensus: {consensus.value} ({consensus_count}/5). "
        f"Buy: {buy_count}, Hold: {hold_count}, Sell: {sell_count}. "
    )

    # Add dissenter highlights
    dissenters = [a for a in analyses if a.action != consensus]
    if dissenters:
        summary += "Dissenters: " + "; ".join(
            f"{d.investor_name} says {d.action.value} (conviction {d.conviction}/10)"
            for d in dissenters
        )

    return MergedReport(
        ticker=ticker,
        consensus_action=consensus,
        consensus_count=consensus_count,
        total_personas=len(analyses),
        analyses=analyses,
        summary=summary,
    )


# ═══════════════════════════════════════════════════════════════
# Pipeline helpers
# ═══════════════════════════════════════════════════════════════

def _run_pipeline(ticker: str) -> PipelineResult:
    """Run the full TradingAgents pipeline."""
    llm = _get_llm()

    result = PipelineResult(ticker=ticker)

    if llm is None:
        result.error = (
            "No LLM configured. Set OPENAI_API_KEY or TRADING_MCP_MODEL "
            "to enable the trading pipeline."
        )
        return result

    if not _crewai_available():
        result.error = "crewai package not installed. Run: pip install crewai"
        return result

    try:
        from crewai import Agent, Task, Crew, Process
        from agents.analysts import (
            create_fundamentals_analyst,
            create_sentiment_analyst,
            create_news_analyst,
            create_market_analyst,
        )
        from agents.debators import (
            create_bull_researcher,
            create_bear_researcher,
            create_research_manager,
        )
        from agents.trader import create_trader
        from agents.risk_manager import (
            create_aggressive_analyst,
            create_conservative_analyst,
            create_neutral_analyst,
            create_portfolio_manager,
        )

        # ── Stage 1: Analyst reports ──
        analysts = [
            ("fundamentals", create_fundamentals_analyst(llm=llm)),
            ("sentiment", create_sentiment_analyst(llm=llm)),
            ("news", create_news_analyst(llm=llm)),
            ("market", create_market_analyst(llm=llm)),
        ]

        analyst_reports = {}
        for key, agent in analysts:
            task = Task(
                description=(
                    f"Analyze {ticker} from your specialist perspective. "
                    f"Write a detailed report with specific, actionable insights. "
                    f"Use data where available; note where data is unavailable."
                ),
                expected_output=f"A detailed {key} analysis report for {ticker}",
                agent=agent,
            )
            crew = Crew(agents=[agent], tasks=[task], verbose=False)
            report = crew.kickoff()
            analyst_reports[key] = str(report) if report else f"No {key} report produced"

        result.analyst_reports = analyst_reports

        # ── Stage 2: Bull-bear debate ──
        bull = create_bull_researcher(llm=llm)
        bear = create_bear_researcher(llm=llm)
        manager = create_research_manager(llm=llm)

        # Bull case
        bull_task = Task(
            description=(
                f"Build the bull case for {ticker}. Use these analyst reports:\n\n"
                + "\n\n".join(f"=== {k} ===\n{v}" for k, v in analyst_reports.items())
            ),
            expected_output="A detailed bull case",
            agent=bull,
        )
        bull_result = Crew(agents=[bull], tasks=[bull_task], verbose=False).kickoff()

        # Bear case
        bear_task = Task(
            description=(
                f"Build the bear case for {ticker}. Use these analyst reports:\n\n"
                + "\n\n".join(f"=== {k} ===\n{v}" for k, v in analyst_reports.items())
            ),
            expected_output="A detailed bear case",
            agent=bear,
        )
        bear_result = Crew(agents=[bear], tasks=[bear_task], verbose=False).kickoff()

        # Research manager synthesizes
        manager_task = Task(
            description=(
                f"Synthesize the bull-bear debate for {ticker} into an investment plan.\n\n"
                f"Bull case:\n{bull_result}\n\nBear case:\n{bear_result}"
            ),
            expected_output="Investment plan with recommendation and rationale",
            agent=manager,
        )
        plan_result = Crew(agents=[manager], tasks=[manager_task], verbose=False).kickoff()
        result.debate_verdict = str(plan_result) if plan_result else ""

        # ── Stage 3: Trader ──
        trader = create_trader(llm=llm)
        trader_task = Task(
            description=(
                f"Convert this investment plan into a concrete transaction proposal "
                f"for {ticker}:\n\n{plan_result}"
            ),
            expected_output="Transaction proposal with action, entry, stop loss",
            agent=trader,
        )
        trader_result = Crew(agents=[trader], tasks=[trader_task], verbose=False).kickoff()
        # ponytail: parse trader output for structured fields — v1 stores raw string
        result.trader_proposal = TraderProposal(
            action=TraderAction.HOLD,
            reasoning=str(trader_result) if trader_result else "",
        )

        # ── Stage 4: Risk debate ──
        aggressive = create_aggressive_analyst(llm=llm)
        conservative = create_conservative_analyst(llm=llm)
        neutral = create_neutral_analyst(llm=llm)

        risk_reports = {}
        for key, agent in [("aggressive", aggressive), ("conservative", conservative), ("neutral", neutral)]:
            risk_task = Task(
                description=(
                    f"Evaluate the trader's proposal for {ticker} from your {key} "
                    f"risk perspective:\n\n{trader_result}"
                ),
                expected_output=f"A {key} risk assessment",
                agent=agent,
            )
            risk_result = Crew(agents=[agent], tasks=[risk_task], verbose=False).kickoff()
            risk_reports[key] = str(risk_result) if risk_result else ""

        result.risk_assessments = risk_reports

        # ── Stage 5: Portfolio Manager ──
        pm = create_portfolio_manager(llm=llm)
        pm_task = Task(
            description=(
                f"Render the final decision for {ticker}. Consider:\n\n"
                f"Analyst Reports:\n" + "\n".join(f"- {k}" for k in analyst_reports) + "\n\n"
                f"Investment Plan:\n{plan_result}\n\n"
                f"Trader Proposal:\n{trader_result}\n\n"
                f"Risk Assessments:\n" + "\n".join(
                    f"- {k}: {v}" for k, v in risk_reports.items()
                )
            ),
            expected_output="Final portfolio decision with rating and thesis",
            agent=pm,
        )
        pm_result = Crew(agents=[pm], tasks=[pm_task], verbose=False).kickoff()

        result.portfolio_decision = PortfolioDecision(
            ticker=ticker,
            rating=PortfolioRating.HOLD,
            executive_summary=str(pm_result)[:500] if pm_result else "",
            investment_thesis=str(pm_result) if pm_result else "",
            risk_assessment="See risk assessments above",
        )

    except Exception as e:
        result.error = f"Pipeline error: {e}"

    return result


# ═══════════════════════════════════════════════════════════════
# MCP Tools
# ═══════════════════════════════════════════════════════════════

@app.tool
def list_personas() -> str:
    """List available famous investor personas and their investment philosophies."""
    return _personas_text()


@app.tool
def analyze_ticker(ticker: str) -> str:
    """Five famous investor personas analyze a stock and produce a consensus report.

    Args:
        ticker: Stock ticker symbol (e.g. AAPL, 000001, 600519)
    """
    result = _run_persona_analysis(ticker)
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)


@app.tool
def bull_bear_debate(ticker: str, thesis: str = "") -> str:
    """Bull vs bear researcher debate with research manager verdict.

    Args:
        ticker: Stock ticker symbol
        thesis: Optional starting thesis to frame the debate
    """
    llm = _get_llm()
    if llm is None:
        return json.dumps({
            "error": "No LLM configured. Set OPENAI_API_KEY or TRADING_MCP_MODEL.",
            "ticker": ticker,
        }, ensure_ascii=False, indent=2)

    if not _crewai_available():
        return json.dumps({
            "error": "crewai package not installed. Run: pip install crewai",
        }, ensure_ascii=False, indent=2)

    try:
        from crewai import Agent, Task, Crew
        from agents.debators import (
            create_bull_researcher,
            create_bear_researcher,
            create_research_manager,
        )

        bull = create_bull_researcher(llm=llm)
        bear = create_bear_researcher(llm=llm)
        manager = create_research_manager(llm=llm)

        context = f" Starting thesis: {thesis}" if thesis else ""

        bull_task = Task(
            description=f"Build the bull case for {ticker}.{context}",
            expected_output="A detailed bull case",
            agent=bull,
        )
        bull_result = Crew(agents=[bull], tasks=[bull_task], verbose=False).kickoff()

        bear_task = Task(
            description=f"Build the bear case for {ticker}.{context}",
            expected_output="A detailed bear case",
            agent=bear,
        )
        bear_result = Crew(agents=[bear], tasks=[bear_task], verbose=False).kickoff()

        manager_task = Task(
            description=(
                f"Synthesize the bull-bear debate for {ticker} into an investment plan.\n\n"
                f"Bull case:\n{bull_result}\n\nBear case:\n{bear_result}"
            ),
            expected_output="Investment plan with recommendation and rationale",
            agent=manager,
        )
        plan_result = Crew(agents=[manager], tasks=[manager_task], verbose=False).kickoff()

        return json.dumps({
            "ticker": ticker,
            "bull_case": str(bull_result),
            "bear_case": str(bear_result),
            "verdict": str(plan_result),
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Debate error: {e}", "ticker": ticker}, ensure_ascii=False, indent=2)


@app.tool
def risk_debate(ticker: str, proposal_json: str = "{}") -> str:
    """Aggressive/conservative/neutral risk debate with portfolio manager final decision.

    Args:
        ticker: Stock ticker symbol
        proposal_json: Trader proposal as JSON string (optional, will generate if empty)
    """
    llm = _get_llm()
    if llm is None:
        return json.dumps({
            "error": "No LLM configured. Set OPENAI_API_KEY or TRADING_MCP_MODEL.",
            "ticker": ticker,
        }, ensure_ascii=False, indent=2)

    if not _crewai_available():
        return json.dumps({
            "error": "crewai package not installed. Run: pip install crewai",
        }, ensure_ascii=False, indent=2)

    try:
        from crewai import Task, Crew
        from agents.risk_manager import (
            create_aggressive_analyst,
            create_conservative_analyst,
            create_neutral_analyst,
            create_portfolio_manager,
        )

        aggressive = create_aggressive_analyst(llm=llm)
        conservative = create_conservative_analyst(llm=llm)
        neutral = create_neutral_analyst(llm=llm)
        pm = create_portfolio_manager(llm=llm)

        context = f" Proposal: {proposal_json}" if proposal_json != "{}" else ""

        risk_reports = {}
        for key, agent in [("aggressive", aggressive), ("conservative", conservative), ("neutral", neutral)]:
            risk_task = Task(
                description=(
                    f"Evaluate the trading proposal for {ticker} from your {key} "
                    f"risk perspective.{context}"
                ),
                expected_output=f"A {key} risk assessment",
                agent=agent,
            )
            risk_result = Crew(agents=[agent], tasks=[risk_task], verbose=False).kickoff()
            risk_reports[key] = str(risk_result) if risk_result else ""

        pm_task = Task(
            description=(
                f"Render the final decision for {ticker} after reviewing risk assessments:\n\n"
                + "\n\n".join(f"=== {k} ===\n{v}" for k, v in risk_reports.items())
            ),
            expected_output="Final portfolio decision with rating and thesis",
            agent=pm,
        )
        pm_result = Crew(agents=[pm], tasks=[pm_task], verbose=False).kickoff()

        return json.dumps({
            "ticker": ticker,
            "risk_assessments": risk_reports,
            "portfolio_decision": str(pm_result),
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Risk debate error: {e}", "ticker": ticker}, ensure_ascii=False, indent=2)


@app.tool
def full_pipeline(ticker: str) -> str:
    """End-to-end TradingAgents pipeline: analysts → debate → trader → risk → decision.

    Args:
        ticker: Stock ticker symbol (e.g. AAPL, 000001)
    """
    result = _run_pipeline(ticker)
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# Startup: register tools in daas.db
# ═══════════════════════════════════════════════════════════════

_startup_msg = _register_in_registry()


if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
