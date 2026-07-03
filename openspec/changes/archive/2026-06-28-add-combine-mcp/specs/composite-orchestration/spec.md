## ADDED Requirements

### Requirement: Chained tools run a linear pipeline across upstreams

The system SHALL support defining a chained tool as an ordered list of steps, where each step calls one tool on one upstream. Steps execute sequentially.

#### Scenario: Three-step chain with cross-step references

- **WHEN** a chain `my_brief` has steps `[{akshare, stock_zh_a_hist, {symbol: "000001"}}, {akshare, stock_news_em, {}}, {daas, fetch_data, {close: "$step[0].close", sentiment: "$prev.sentiment"}}]`
- **THEN** calling `my_brief` SHALL execute step 0 on akshare, then step 1 on akshare, then step 2 on daas with `close` set to the `close` field of step 0's result and `sentiment` set to the `sentiment` field of step 1's result, and return step 2's result

### Requirement: Step inputs resolve `$step[N]` and `$prev` references

The system SHALL resolve input values against the list of completed step results. A value beginning with `$step[N].` references step N (0-based) of the chain; a value beginning with `$prev.` references the immediately prior step; all other values are literals. Path resolution after the prefix is dot-path lookup into the referenced step's result object.

#### Scenario: Literal input

- **WHEN** a step input is `{"symbol": "000001"}`
- **THEN** the value `000001` is passed to the upstream tool verbatim

#### Scenario: Previous-step reference via `$prev`

- **WHEN** a step input is `{"source": "$prev.close"}` and the previous step returned `{"close": 12.34, "open": 12.0}`
- **THEN** the value `12.34` is passed as `source` to the upstream tool

#### Scenario: Any-prior-step reference via `$step[N]`

- **WHEN** a step 2 input is `{"close": "$step[0].close"}` and step 0 returned `{"close": 12.34}`
- **THEN** the value `12.34` is passed as `close` to the upstream tool, even though it is not the immediately prior step

### Requirement: Chained tools fail fast

The system SHALL abort a chain on the first step that errors and SHALL surface that step's error to the caller. No partial results from later steps.

#### Scenario: Upstream tool errors mid-chain

- **WHEN** step 2 of a chain calls a tool that does not exist on its upstream
- **THEN** the chain SHALL return an error identifying the failing step and SHALL NOT execute step 3

### Requirement: Chains are linear only

The system SHALL support linear pipelines only. Branching, conditionals, and loops are not supported in v1.

#### Scenario: Unsupported branching is rejected

- **WHEN** a chain step definition includes a conditional or branch construct
- **THEN** the system SHALL reject the chain definition at `add_chained_tool` time with a clear error
