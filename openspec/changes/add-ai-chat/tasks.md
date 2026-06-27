## 1. Dependencies & Setup

- [x] 1.1 Add AI SDK packages to `dashboard/package.json`: `ai`, `@ai-sdk/react`, `@ai-sdk/anthropic`, `@ai-sdk/openai`, `@ai-sdk/google`, `@ai-sdk/mcp`, `@modelcontextprotocol/sdk`, `react-markdown`, `react-syntax-highlighter`
- [x] 1.2 Run `npm install` from `dashboard/` to install new dependencies
- [x] 1.3 Add `ANTHROPIC_API_KEY`, `AI_PROVIDER`, `AI_MODEL`, `MCP_SERVER` to `dashboard/.env.local`

## 2. Provider Factory

- [x] 2.1 Create `dashboard/src/lib/providers.ts` with `getModel()` function that switches on `AI_PROVIDER` env var to return the correct AI SDK model
- [x] 2.2 Handle missing API keys with clear error messages per provider

## 3. MCP Client Singleton

- [x] 3.1 Create `dashboard/src/lib/mcp-client.ts` with singleton `getMCPClient()` that spawns `leader-mcp` via `Experimental_StdioMCPTransport`
- [x] 3.2 Add health check and automatic reconnect on connection drop
- [x] 3.3 Add `getMCPTools()` helper that calls `client.tools()` and caches the result
- [x] 3.4 Support configurable server via `MCP_SERVER` env var

## 4. Chat API Route

- [x] 4.1 Create `dashboard/src/app/api/chat/route.ts` with `POST` handler
- [x] 4.2 Implement `streamText` with provider from factory, MCP tools, and system prompt that instructs AI about echarts output
- [x] 4.3 Return streaming response using `createUIMessageStreamResponse` + `toUIMessageStream`
- [x] 4.4 Add tool result truncation (10KB limit) with `[truncated]` marker
- [x] 4.5 Set `maxDuration = 120` for long-running tool calls

## 5. Chat Store (localStorage)

- [x] 5.1 Create `dashboard/src/lib/chat-store.ts` with `loadConversations()`, `saveConversation()`, `deleteConversation()`, `getConversation(id)` functions
- [x] 5.2 Cap conversations at 50 messages each, auto-prune older than 30 days

## 6. Chat UI Components

- [x] 6.1 Create `dashboard/src/components/chat/chat-input.tsx` — textarea + send button, auto-resize, Enter to send, Shift+Enter for newline
- [x] 6.2 Create `dashboard/src/components/chat/message-list.tsx` — scrollable container, auto-scroll to bottom on new messages
- [x] 6.3 Create `dashboard/src/components/chat/message-bubble.tsx` — renders message parts: text (Markdown), reasoning, tool-call, tool-result, echarts
- [x] 6.4 Create `dashboard/src/components/chat/reasoning-block.tsx` — collapsible "Thinking..." section, collapsed by default, shows reasoning text
- [x] 6.5 Create `dashboard/src/components/chat/tool-call-card.tsx` — expandable card showing tool name, args (formatted JSON), result/error
- [x] 6.6 Create `dashboard/src/components/chat/echarts-block.tsx` — detects ` ```echarts` blocks, parses JSON, renders with existing `EChartsWrapper`, shows error on invalid config

## 7. Chat Page

- [x] 7.1 Create `dashboard/src/app/chat/page.tsx` — client component using `useChat` from `@ai-sdk/react` with `DefaultChatTransport`
- [x] 7.2 Wire up `useChat` options: `id` (conversation ID), `initialMessages` (from localStorage), `onToolCall` (optional client-side tool handling)
- [x] 7.3 Implement message part rendering loop: iterate `message.parts`, render each part type appropriately
- [x] 7.4 Add "New Chat" button that creates a fresh conversation with new UUID
- [x] 7.5 Add conversation switcher sidebar (list of saved conversations, click to load)
- [x] 7.6 Handle error states: connection lost, API key missing, MCP server unavailable

## 8. Navigation Update

- [x] 8.1 Add "Chat" link to `dashboard/src/components/nav.tsx` LINKS array, pointing to `/chat`

## 9. Polish & Verification

- [ ] 9.1 Test streaming chat with Anthropic provider (requires ANTHROPIC_API_KEY)
- [ ] 9.2 Test streaming chat with OpenAI provider (switch env var, requires OPENAI_API_KEY)
- [ ] 9.3 Test MCP tool calls: ask "list all harnesses" and verify tool card appears with results (requires running leader-mcp)
- [ ] 9.4 Test ECharts rendering: ask "show me a bar chart of..." and verify chart renders
- [ ] 9.5 Test reasoning display: use Claude with thinking enabled, verify "Thinking..." block appears
- [ ] 9.6 Test chat persistence: send messages, refresh page, verify conversation restored
- [ ] 9.7 Test error states: remove API key, verify clear error message
- [x] 9.8 Run `npm run dev` and verify no build errors
