## ADDED Requirements

### Requirement: Structured AI extraction
The system SHALL provide a tool `ai_extract` that takes report section text plus a JSON Schema and returns validated structured records produced by the configured OpenAI-compatible LLM endpoint (shared `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`), requesting JSON output and validating it against the supplied schema.

#### Scenario: Extract financial line items
- **WHEN** the agent calls `ai_extract` with section text and a schema for `{item, amount, currency}`
- **THEN** the system returns a list of records conforming to the schema, validated before return

#### Scenario: Schema-violating model output
- **WHEN** the LLM output does not conform to the supplied JSON Schema
- **THEN** the system retries once with a corrective prompt, then returns an error if still invalid

### Requirement: Configurable provider and model
The LLM endpoint and model SHALL be read from the shared environment (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`), and the tool SHALL return a clear error when the API key is absent rather than calling the API.

#### Scenario: No API key configured
- **WHEN** `ai_extract` is called with `LLM_API_KEY` unset
- **THEN** the system returns an error stating the key is missing and does not make a network call

### Requirement: Input truncation safety
The system SHALL truncate section text to a configurable `max_chars` (default 12000) before sending to the LLM and SHALL report whether truncation occurred in the result.

#### Scenario: Oversized section
- **WHEN** the input text exceeds `max_chars`
- **THEN** the system truncates the text, proceeds with extraction, and includes `truncated: true` in the result
