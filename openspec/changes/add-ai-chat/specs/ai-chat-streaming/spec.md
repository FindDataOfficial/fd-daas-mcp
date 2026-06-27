## ADDED Requirements

### Requirement: Streaming AI chat with multi-provider support

The system SHALL provide a chat page at `/chat` that streams AI responses in real-time using the Vercel AI SDK, with provider selection driven by `AI_PROVIDER` and `AI_MODEL` environment variables.

#### Scenario: User sends a message and receives streaming response

- **WHEN** user types a message and submits
- **THEN** the message appears in the chat immediately, and the AI response streams in character-by-character with no full-page reload

#### Scenario: Provider configured via environment

- **WHEN** `AI_PROVIDER=anthropic` and `AI_MODEL=claude-sonnet-4-6` are set
- **THEN** the `/api/chat` route uses `@ai-sdk/anthropic` with model `claude-sonnet-4-6`

#### Scenario: Provider switch to OpenAI

- **WHEN** `AI_PROVIDER=openai` and `AI_MODEL=gpt-4o` are set
- **THEN** the `/api/chat` route uses `@ai-sdk/openai` with model `gpt-4o` without any code changes

#### Scenario: OpenRouter provider

- **WHEN** `AI_PROVIDER=openrouter` is set with `AI_MODEL=anthropic/claude-sonnet-4`
- **THEN** the route uses `@openrouterteam/ai-sdk-provider` with the specified model

#### Scenario: Local Ollama provider

- **WHEN** `AI_PROVIDER=ollama` and `AI_MODEL=llama3` are set
- **THEN** the route uses `@ai-sdk/openai-compatible` pointing to `http://localhost:11434/v1`

#### Scenario: Missing API key shows clear error

- **WHEN** `ANTHROPIC_API_KEY` is not set and provider is anthropic
- **THEN** the chat page displays "Missing API key: set ANTHROPIC_API_KEY in dashboard/.env.local" instead of a generic 500 error

### Requirement: Reasoning/thinking display

The system SHALL display AI reasoning (extended thinking) content in collapsible sections within the chat.

#### Scenario: Claude returns reasoning

- **WHEN** the AI model returns reasoning parts in the stream
- **THEN** the reasoning is shown in an expandable "Thinking..." section above the final response, collapsed by default

#### Scenario: Model does not support reasoning

- **WHEN** the configured model does not emit reasoning parts (e.g., GPT-4o without reasoning)
- **THEN** no collapsible thinking section appears — the UI degrades gracefully

### Requirement: Chat history persistence in localStorage

The system SHALL persist chat messages to `localStorage` keyed by conversation ID, and load them on page revisit.

#### Scenario: Messages survive page refresh

- **WHEN** user sends messages, refreshes the page, and returns to `/chat`
- **THEN** the previous conversation is restored from localStorage and displayed

#### Scenario: Multiple conversations

- **WHEN** user creates a new conversation via "New Chat" button
- **THEN** a new conversation is started with a unique ID, and previous conversations remain accessible

#### Scenario: Clear conversation

- **WHEN** user clicks "Clear" on a conversation
- **THEN** that conversation is removed from localStorage

### Requirement: Chat UI with message rendering

The system SHALL render chat messages with Markdown formatting, code syntax highlighting, and proper user/AI distinction.

#### Scenario: Markdown rendering

- **WHEN** AI responds with markdown-formatted text (bold, lists, tables, links)
- **THEN** the content is rendered as HTML with appropriate styling

#### Scenario: Code blocks without echarts

- **WHEN** AI outputs a code block with language `python` or `sql`
- **THEN** it is rendered with syntax highlighting but not treated as a chart
