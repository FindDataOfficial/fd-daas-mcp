# trading-pipeline Specification

## Purpose
TBD - created by syncing change add-trading-mcp. Update after archive.

Defines the multi-stage CrewAI agent pipeline that runs end-to-end for a single ticker: four analyst agents (Fundamentals, Sentiment, News, Market/Technical) → bull/bear debate synthesized by a research manager → trader agent proposal → three risk-analyst debate (Aggressive, Conservative, Neutral) → portfolio manager final decision. Exposed via the `full_pipeline` tool.

## Requirements

### Requirement: Analyst team produces four research reports

The system SHALL implement four analyst agents (Fundamentals, Sentiment, News, Market/Technical) that produce structured research reports for a given ticker.

#### Scenario: Fundamentals analyst produces a report

- **WHEN** the full pipeline runs for a ticker
- **THEN** the fundamentals analyst produces a report covering financial health, valuation metrics, and company fundamentals

#### Scenario: Sentiment analyst produces a report

- **WHEN** the full pipeline runs for a ticker
- **THEN** the sentiment analyst produces a report covering market sentiment signals

#### Scenario: News analyst produces a report

- **WHEN** the full pipeline runs for a ticker
- **THEN** the news analyst produces a report covering relevant macro and company news

#### Scenario: Market analyst produces a report

- **WHEN** the full pipeline runs for a ticker
- **THEN** the market/technical analyst produces a report covering price trends and technical indicators

### Requirement: Bull-bear debate yields a research plan

The system SHALL implement bull and bear researcher agents that debate the analyst reports, with a research manager synthesizing the debate into a structured investment plan.

#### Scenario: Bull researcher argues the bullish case

- **WHEN** `bull_bear_debate` is called with analyst reports
- **THEN** the bull researcher produces arguments for buying based on positive signals in the data

#### Scenario: Bear researcher argues the bearish case

- **WHEN** `bull_bear_debate` is called with analyst reports
- **THEN** the bear researcher produces arguments for selling/avoiding based on negative signals in the data

#### Scenario: Research manager synthesizes debate

- **WHEN** bull and bear researchers have each presented their case
- **THEN** the research manager produces a plan with a clear recommendation (Buy/Overweight/Hold/Underweight/Sell) and supporting rationale

### Requirement: Trader produces concrete proposal

The system SHALL implement a trader agent that converts the research plan into a concrete transaction proposal.

#### Scenario: Trader proposes entry

- **WHEN** the research plan recommends Buy
- **THEN** the trader produces a proposal with suggested entry price, stop loss, and position sizing guidance

#### Scenario: Trader proposes exit or hold

- **WHEN** the research plan recommends Sell or Hold
- **THEN** the trader produces a proposal with reasoning and any suggested exit parameters

### Requirement: Risk debate produces final decision

The system SHALL implement three risk analyst agents (Aggressive, Conservative, Neutral) that debate the trader's proposal, with a portfolio manager making the final decision.

#### Scenario: Three risk perspectives debate

- **WHEN** `risk_debate` is called with a trader proposal
- **THEN** the aggressive, conservative, and neutral risk analysts each produce their assessment

#### Scenario: Portfolio manager renders final decision

- **WHEN** all three risk analysts have presented their views
- **THEN** the portfolio manager produces a final `PortfolioDecision` with rating, executive summary, investment thesis, and risk assessment

### Requirement: Full pipeline runs end-to-end

The system SHALL provide a `full_pipeline` tool that runs the complete agent pipeline (analysts → debate → trader → risk → decision) for a single ticker.

#### Scenario: Complete pipeline execution

- **WHEN** `full_pipeline("000001")` is called
- **THEN** it returns a structured result containing analyst reports, debate verdict, trader proposal, risk assessments, and the final portfolio decision

#### Scenario: Pipeline handles errors gracefully

- **WHEN** an intermediate agent fails (e.g., data unavailable)
- **THEN** the pipeline SHALL report which stage failed and return partial results rather than crashing
