# collection-chat

## ADDED Requirements

### Requirement: Chat surface bound to active collection

The dashboard SHALL render a chat pane that is bound to exactly one collection at a time. When the active collection changes, a fresh chat session SHALL start (prior session messages remain in history but are no longer the active context).

#### Scenario: Chat is empty for an empty collection

- **WHEN** the active collection has zero items and the user types a message
- **THEN** the chat replies that the collection is empty and prompts the user to add datasources before asking a data question

#### Scenario: Switching collections starts a fresh chat

- **WHEN** the user has an in-progress chat in collection A and switches to collection B
- **THEN** the chat pane displays an empty conversation for B; A's history is preserved and re-displayed if the user switches back to A

### Requirement: Collection context is sent with every chat turn

For every chat turn the dashboard SHALL build a system context from the active collection's items: each item's datasource name, label, form (if any), section name (if any), and `instruction` text. The collection's instructions become the model's tool-routing grammar (`mcp=… tool=… param=k=v` as documented in `daas-mcp`).

#### Scenario: Context includes section instructions

- **WHEN** the active collection contains a section whose `instruction` says `mcp=edgar tool=get_filing param=accession=…`
- **THEN** that instruction is included verbatim in the model's system prompt so the model can produce the correct routing string

#### Scenario: Context is rebuilt on each turn

- **WHEN** the user adds or removes a collection item between two chat turns
- **THEN** the next turn's context reflects the updated item list (no manual refresh required)

### Requirement: Tool-call dispatch to daas-mcp `fetch_data`

When the model emits a routing string of the form `mcp=<source> tool=<tool> param=<k>=<v> …` (or otherwise indicates a data call), the chat backend SHALL dispatch it to `daas-mcp`'s `fetch_data` function (or directly to the named source adapter) and SHALL return the result to the model as a tool result before continuing the turn.

#### Scenario: Model requests a fetch

- **WHEN** the model emits `mcp=edgar tool=get_filing param=accession=0000320193-24-000123`
- **THEN** the chat backend calls the equivalent of `fetch_data("edgar_get_filing", {"accession": "0000320193-24-000123"})`, parses the result, and feeds it back as a tool message

#### Scenario: Fetch error is surfaced

- **WHEN** a dispatched fetch raises (e.g. unknown source, API key missing)
- **THEN** the error message is fed back to the model as a tool error so it can apologize / retry / ask a clarifying question, and the error is also shown to the user

#### Scenario: Source not in the active collection is refused

- **WHEN** the model tries to call a datasource that is not in the active collection's items
- **THEN** the chat backend refuses the call with a clear message; the model must work only with sources the user has put in the collection

### Requirement: Chat API route and streaming

The dashboard SHALL expose a `POST /api/chat` route that accepts `{ collection: string, messages: ChatMessage[] }` and streams the assistant response back to the client (server-sent events or fetch streaming). The route reads the LLM API key from the server environment; the key is never exposed to the client.

#### Scenario: Token streaming

- **WHEN** a chat request is in flight
- **THEN** the dashboard renders incremental tokens as they arrive

#### Scenario: Missing API key

- **WHEN** the server has no LLM API key configured
- **THEN** `/api/chat` returns a clear error and the chat pane shows a setup hint pointing to root `.env`
