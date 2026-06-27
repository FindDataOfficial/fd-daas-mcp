"""Agent factories for the trading-mcp server.

All agent factory functions lazy-import crewai, so this package is importable
without crewai installed. list_personas() works crewai-free.
"""

# Persona data is always available (no crewai needed)
from agents.personas import PERSONA_DEFS, _persona_prompt

# Agent factories (lazy-import crewai internally)
from agents.personas import (
    create_buffett_persona,
    create_soros_persona,
    create_lynch_persona,
    create_dalio_persona,
    create_simons_persona,
)
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
