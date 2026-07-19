# Investment methods & masters (brainstorm references)

A compact lens library for framing a research goal. The user may reference one
or more to shape what to study, which indicators matter, and what the dashboard
should answer. These extend the five `investor-personas` (Buffett, Soros,
Lynch, Dalio, Simons) with more methods and masters. Pick what fits the goal -
don't pile on.

## Methods

| Method | Core question | What it pushes you to measure |
| --- | --- | --- |
| **Value investing** | What is this worth intrinsically vs. its price? | Valuation ratios (P/E, P/B, EV/EBITDA), margin of safety, dividend yield, book value |
| **Growth investing** | Is earnings/revenue growth durable and accelerating? | Revenue/earnings growth %, PEG, runway, retention, market share |
| **GARP (Growth at a Reasonable Price)** | Does growth justify the price? | PEG <= 1, earnings growth vs. P/E |
| **Momentum / trend-following** | Is the price trend up and broad? | SMA/EMA crossovers, relative strength, 52-week high, rate of change |
| **Macro / reflexivity** | What macro regime is this, and is the trend self-reinforcing? | Rates, FX, credit, index breadth, correlation, sentiment |
| **Quantitative / statistical** | Is there an edge that is systematic and testable? | Mean reversion, z-score, rolling std, factor exposure, backtested signal |
| **Factor / risk-parity** | Which factors drive returns, and is risk balanced? | Value/size/momentum/quality/volatility factors, beta, volatility, correlation |
| **Quality / fundamentals** | Is the business durable and well-run? | ROE/ROIC, margins, debt/equity, free cash flow, accruals |

## Masters

| Master | Lens (one line) |
| --- | --- |
| **Benjamin Graham** | Buy with a margin of safety below intrinsic value; the market is a voting machine short-term, weighing machine long-term. |
| **Philip Fisher** | Growth via deep qualitative research on the business, management, and R&D pipeline ("scuttlebutt"). |
| **Warren Buffett** | Wonderful companies at fair prices; moat + management + long holding period; Mr. Market. |
| **Charlie Munger** | Multi-disciplinary mental models; avoid stupidity; quality over cheapness; "all I want to know is where I'm going to die." |
| **Peter Lynch** | Invest in what you understand (GARP); "tenbagger" growth from everyday observation; PEG. |
| **John Bogle** | Low-cost broad index ownership; don't look for needles, buy the haystack; minimize friction. |
| **Harry Markowitz** | Diversification via the efficient frontier; portfolio risk is about covariance, not individual risk. |
| **Ray Dalio** | All-weather risk parity; understand the economic machine (debt cycle); principles + radical transparency. |
| **George Soros** | Reflexivity - bias shapes fundamentals which shape bias; bet big when you're right, survive when wrong. |
| **Jim Simons** | Pure quantitative/statistical edge; short holding periods; let the model decide, humans don't override. |
| **David Swensen** | Long-horizon, illiquidity-premium, alternative-asset diversification for institutions. |
| **Stanley Druckenmiller** | Macro, size your convictions, concentrate when the asymmetry is real, preserve capital above all. |
| **Nassim Taleb** | Antifragility and tail-risk/barbell strategies; price optionality; don't blow up on black swans. |
| **Jesse Livermore** | Trend-following discipline; pyramid into winners, cut losers fast; the big money is in the sitting. |
| **Richard Wyckoff** | Price/volume and the "composite operator" - accumulation vs. distribution phases. |

## How to use these in a brainstorm

- When the user names a method or master, ask how it maps to the entity they
  picked: e.g. "Graham-style on BYD -> which valuation ratios, and what's your
  margin-of-safety trigger?"
- Multiple lenses are fine - note the primary one and any secondary (e.g.
  "primary: momentum; secondary: fundamentals for conviction").
- The lens drives the **indicators** section of the plan doc: a momentum goal ->
  SMA/EMA/RSI/relative-strength; a value goal -> P/E, P/B, EV/EBITDA, dividend
  yield; a macro goal -> index breadth, rates, correlation.
- The lens drives the **dashboard shape**: momentum -> price + moving-average
  overlay + RSI pane; value -> valuation-ratio history vs. peers; macro ->
  multi-series regime panel.
