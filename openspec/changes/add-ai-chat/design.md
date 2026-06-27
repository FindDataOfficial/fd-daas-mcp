## Context

The dashboard is a Next.js 15 App Router app at `dashboard/` using sql.js (WASM) for direct SQLite reads. It has three existing pages (databases, cron, datasources) with Tailwind CSS + ECharts charts. There are no AI SDK dependencies installed. The MCP ecosystem includes `leader-mcp` (12 tools) and several other MCP servers configured in `.mcp.json` via stdio transport. The dashboard currently has no way to interact with MCP tools conversationally.

## Goals / Non-Goals

**Goals:**
- Add a `/chat` page with streaming AI responses, MCP tool calls, and ECharts rendering
- Support multiple LLM providers via a single env-configurable switch
- Reuse existing `EChartsWrapper` component for chart rendering
- Keep chat history in localStorage (zero database changes)
- Singleton MCP client to avoid spawning a Python process per request

**Non-Goals:**
- Multi-user authentication or authorization
- Server-side chat history persistence (DB) — v1 uses localStorage
- Multiple MCP servers simultaneously (single server, configurable)
- Real-time collaboration or WebSocket transport
- Docker deployment changes
- Mobile responsive design for chat

## Decisions

### Decision 1: AI SDK v5 with `createUIMessageStreamResponse` + `toUIMessageStream`

**Chosen**: `ai` v5, using `streamText` on the server, `useChat` from `@ai-sdk/react` on the client.

**Rationale**: AI SDK v5 is the current stable release. The v5 API (`createUIMessageStreamResponse` with `toUIMessageStream`) is well-documented and the migration path to v6/v7 is clear. v6/v7 beta APIs (`toUIMessageStream` and `createUIMessageStreamResponse` as stateless helpers) are still in flux.

**Alternatives considered**:
- `ai` v6/v7 beta: Newer API but breaking changes still happening. v5 is safer for now.
- Raw SSE with custom TransformStream: More control but reimplements what the AI SDK already handles (tool calls, reasoning parts, message IDs).
- Server Actions (RSC): Doesn't support streaming tool calls cleanly. Route handler is the canonical pattern.

### Decision 2: `@ai-sdk/mcp` for MCP client (not raw `@modelcontextprotocol/sdk`)

**Chosen**: `@ai-sdk/mcp` with `createMCPClient` + `Experimental_StdioMCPTransport`.

**Rationale**: `@ai-sdk/mcp` automatically converts MCP tools to AI SDK tools (`client.tools()` returns tools ready for `streamText`). With the raw SDK, we'd need to manually map MCP tool schemas to AI SDK tool schemas. The `@ai-sdk/mcp` package handles this conversion, including Zod schema inference.

**Alternatives considered**:
- Raw `@modelcontextprotocol/sdk` `Client` + `StdioClientTransport`: Works but requires manual tool schema conversion. More code, more bugs.
- HTTP/SSE transport to a long-running MCP process: Adds operational complexity (need to manage the process separately). Stdio spawn-on-demand with singleton is simpler.

### Decision 3: Singleton MCP client (not per-request)

**Chosen**: Module-level singleton in `src/lib/mcp-client.ts`. On first request, spawn the Python process and connect. On connection drop, reconnect. On error, throw (let the API route handle it).

**Rationale**: Spawning a Python process (`fastmcp run server.py`) takes 1-3 seconds. Doing this per request is unacceptable. A singleton keeps the process warm.

```
┌─────────────────────────────────────────────────────┐
│ mcp-client.ts (singleton)                           │
│                                                     │
│  let _client: MCPClient | null = null               │
│                                                     │
│  export async function getMCPClient() {              │
│    if (_client && connected) return _client          │
│    if (!_client) {                                   │
│      _client = await createMCPClient({               │
│        transport: new Experimental_StdioMCPTransport(│
│          { command: 'fastmcp', args: [...] }         │
│        )                                            │
│      })                                             │
│    }                                                │
│    return _client                                    │
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

**Risk**: If the Python process hangs, all subsequent requests fail. Mitigation: add a 30s health check + reconnect in `getMCPClient()`.

### Decision 4: Provider factory pattern

**Chosen**: Switch on `AI_PROVIDER` env var in the route handler.

```typescript
function getModel() {
  switch (process.env.AI_PROVIDER) {
    case 'openai':     return openai(process.env.AI_MODEL || 'gpt-4o');
    case 'google':     return google(process.env.AI_MODEL || 'gemini-2.5-flash');
    case 'openrouter': return openrouter(process.env.AI_MODEL || 'anthropic/claude-sonnet-4');
    case 'ollama':     return createOpenAICompatible({ name: process.env.AI_MODEL || 'llama3', baseURL: 'http://localhost:11434/v1' });
    default:           return anthropic(process.env.AI_MODEL || 'claude-sonnet-4-6');
  }
}
```

**Rationale**: One env var switch, no code changes needed. Default to Anthropic (best MCP tool-use performance). Each provider package is tree-shakeable — only the used provider is loaded at runtime (dynamic import).

### Decision 5: ` ```echarts` code blocks (not custom tool)

**Chosen**: System prompt instructs the AI to output ECharts configurations as ` ```echarts` JSON blocks. Client-side parser detects these blocks and renders them with `EChartsWrapper`.

**Rationale**: This is the lazy approach. No custom AI SDK tool needed, no tool registration, no schema definition. The AI already knows the ECharts option format from its training data. Client-side detection is ~30 lines of code.

**Alternatives considered**:
- Custom `render_chart` tool: More structured but requires defining the full ECharts option schema as a Zod schema (hundreds of properties). Over-engineered for v1.
- Separate chart generation endpoint: Adds complexity without benefit. Inline blocks keep everything in the chat flow.

### Decision 6: localStorage for chat history

**Chosen**: Store conversations as JSON in `localStorage`, keyed by conversation ID. Load on page mount.

**Rationale**: Zero backend changes. No new database tables. Survives page refresh. Simple to implement (~50 lines). For a local-only dashboard, localStorage is sufficient.

**Migration path**: When server-side persistence is needed, add a `conversations` table to `daas.db` and a `/api/conversations` route. The `useChat` hook accepts `initialMessages` — swap localStorage read for API fetch.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| **MCP process hangs** — Python subprocess becomes unresponsive | 30s health check in singleton; reconnect on timeout |
| **Tool results exceed token limits** — MCP tools can return 100KB+ JSON | Truncate tool results to 10KB with `[truncated]` marker; instruct AI to request pagination |
| **AI SDK version churn** — v5→v6→v7 APIs change rapidly | Pin exact versions in `package.json`; the migration path from v5 is documented |
| **localStorage size limits** — conversations could grow large | Cap at 50 messages per conversation; auto-prune conversations older than 30 days |
| **No auth** — dashboard is local-only but AI has full MCP tool access | Acceptable for v1 (same as rest of dashboard); add auth before exposing to network |
| **Cold start** — first request after dashboard restart spawns Python process (1-3s) | Acceptable; show "Connecting to MCP server..." in UI during first request |

## File Structure

```
dashboard/src/
├── app/
│   ├── api/
│   │   └── chat/
│   │       └── route.ts              # POST handler: streamText + MCP tools
│   └── chat/
│       └── page.tsx                  # Client component: useChat + message rendering
├── components/
│   ├── nav.tsx                       # MODIFIED: add "Chat" link
│   └── chat/
│       ├── chat-input.tsx            # Message input + send button
│       ├── message-list.tsx          # Scrollable message container
│       ├── message-bubble.tsx        # Single message: user or AI, with parts
│       ├── reasoning-block.tsx       # Collapsible "Thinking..." section
│       ├── tool-call-card.tsx        # Expandable tool invocation display
│       └── echarts-block.tsx         # Detects ```echarts blocks, renders chart
├── lib/
│   ├── mcp-client.ts                 # Singleton MCP client
│   ├── chat-store.ts                 # localStorage CRUD for conversations
│   └── providers.ts                  # Provider factory (getModel)
```

## Dependencies

```json
{
  "ai": "^5.0.0",
  "@ai-sdk/react": "^1.0.0",
  "@ai-sdk/anthropic": "^2.0.0",
  "@ai-sdk/openai": "^2.0.0",
  "@ai-sdk/google": "^2.0.0",
  "@ai-sdk/mcp": "^0.0.1",
  "@modelcontextprotocol/sdk": "^1.0.0"
}
```

`echarts` and `echarts-for-react` are already installed. `react-markdown` + `react-syntax-highlighter` for Markdown rendering (or a lighter alternative — `marked` with `dangerouslySetInnerHTML` if bundle size matters).

## Open Questions

1. **Should we auto-detect `leader-mcp` path from `.mcp.json`?** Or hardcode it? → Start hardcoded (matching existing `.mcp.json` command), make configurable via env var later.

2. **Should tool results be streamed to the client?** AI SDK v5 supports `toolCallStreaming` (experimental). → Skip for v1 — show tool calls only after completion.

3. **Markdown rendering: `react-markdown` or lighter?** → `react-markdown` is 200KB. For a local dashboard this is fine, but if bundle size matters, use `marked` (20KB) + `dangerouslySetInnerHTML` with sanitization.
