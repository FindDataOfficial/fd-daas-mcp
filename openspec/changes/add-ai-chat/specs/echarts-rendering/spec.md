## ADDED Requirements

### Requirement: AI outputs ECharts configuration in code blocks

The system SHALL detect ` ```echarts` code blocks in AI responses and render them as interactive ECharts charts using the existing `EChartsWrapper` component.

#### Scenario: AI outputs a line chart

- **WHEN** AI response contains ` ```echarts` followed by a valid JSON ECharts option object
- **THEN** the code block is replaced with a rendered ECharts line chart, and the raw JSON is available via "Show Code" toggle

#### Scenario: AI outputs a bar chart

- **WHEN** AI response contains an ECharts configuration with `series.type = 'bar'`
- **THEN** a bar chart is rendered

#### Scenario: Multiple charts in one response

- **WHEN** AI response contains two or more ` ```echarts` blocks
- **THEN** each block is rendered as a separate chart

#### Scenario: Invalid ECharts configuration

- **WHEN** the ` ```echarts` block contains invalid JSON or a broken ECharts config
- **THEN** an error message "Invalid chart configuration" is shown instead of a broken chart, with the raw JSON available for debugging

### Requirement: System prompt instructs AI about echarts output

The system SHALL include instructions in the system prompt that tell the AI how to output ECharts configurations.

#### Scenario: AI is prompted to use echarts

- **WHEN** the chat session starts
- **THEN** the system prompt includes instructions: "When asked to visualize data, output ECharts configurations in ` ```echarts` code blocks using the standard ECharts option format with xAxis, yAxis, and series"

### Requirement: Charts are interactive and responsive

The system SHALL render ECharts with full interactivity (hover tooltips, zoom, pan) and responsive sizing.

#### Scenario: Chart responds to window resize

- **WHEN** user resizes the browser window
- **THEN** all rendered charts resize to fit their container

#### Scenario: Tooltip on hover

- **WHEN** user hovers over a data point on a chart
- **THEN** a tooltip appears showing the exact value and label
