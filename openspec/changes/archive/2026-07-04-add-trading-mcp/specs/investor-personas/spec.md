## ADDED Requirements

### Requirement: Five investor personas are defined

The system SHALL define five investor personas as CrewAI Agent factories, each with a distinct investment philosophy encoded in its role, goal, and backstory.

#### Scenario: Personas are listable

- **WHEN** `list_personas` tool is called
- **THEN** it returns the names and investment philosophies of all five personas: Warren Buffett (value investing), George Soros (macro/reflexivity), Peter Lynch (GARP), Ray Dalio (all-weather/risk-parity), Jim Simons (quantitative/statistical)

#### Scenario: Each persona produces independent analysis

- **WHEN** `analyze_ticker("AAPL")` is called
- **THEN** all five personas produce independent BUY/HOLD/SELL analyses with conviction scores and supporting thesis

### Requirement: Persona agents access financial data

Each investor persona agent SHALL have access to AKShare financial data functions to ground their analysis in real market data.

#### Scenario: Persona fetches stock data

- **WHEN** a persona analyzes a ticker
- **THEN** it can call akshare functions (e.g., `stock_zh_a_hist`) to retrieve price history, financials, or other relevant data

#### Scenario: Persona handles missing data gracefully

- **WHEN** akshare returns no data for a ticker
- **THEN** the persona SHALL state "insufficient data" in its thesis rather than fabricating numbers

### Requirement: Persona analyses are merged into a report

The system SHALL produce a merged report from all five persona analyses, showing the consensus action and highlighting dissenting views.

#### Scenario: Consensus report with dissent

- **WHEN** four personas say BUY and one says HOLD
- **THEN** the merged report SHALL show consensus as BUY (4/5) with the dissenter's reasoning included

#### Scenario: Split decision

- **WHEN** personas are evenly split between BUY and SELL
- **THEN** the merged report SHALL indicate no consensus and present both sides with equal weight
