## Why

The dashboard currently serves as a read-only data browser (databases, cron, datasources), but there's no way to interact with the MCP ecosystem conversationally. Users must switch between Claude Code (for MCP tool queries) and the dashboard (for data visualization). Adding an AI chat page with MCP tool access and ECharts rendering unifies these workflows — query data, run analysis, and visualize results in one place, like Claude Desktop but embedded in the dashboard.

## What Changes

- New `/chat` page in the Next.js dashboard with streaming AI chat UI
- New `/api/chat` route handler using Vercel AI SDK (`ai` v5) with `streamText` + `createUIMessageStreamResponse`
- MCP client integration via `@ai-sdk/mcp` — spawns `leader-mcp` (configurable) via stdio transport, converts MCP tools to AI SDK tools
- Multi-provider support via env config: `AI_PROVIDER` and `AI_MODEL` (Anthropic, OpenAI, Google, OpenRouter, Ollama)
- ECharts rendering: AI outputs ` ```echarts` code blocks, detected and rendered client-side using existing `EChartsWrapper`
- Reasoning/thinking display: Claude's extended thinking streamed and shown in collapsible sections
- Tool call visualization: each MCP tool invocation shown as an expandable card (tool name, args, result)
- `localStorage`-based chat history persistence (v1; no new DB tables)
- New nav item "Chat" in the sidebar

## Capabilities

### New Capabilities

- `ai-chat-streaming`: Streaming AI chat with multi-provider support, reasoning display, and message persistence
- `mcp-tool-integration`: MCP tools auto-discovered from stdio transport and passed to AI as callable tools
- `echarts-rendering`: AI-generated ECharts configurations rendered inline in chat messages

### Modified Capabilities

None — this is entirely new. No existing pages, API routes, or database tables are changed.

## Impact

- New files: `dashboard/src/app/chat/page.tsx`, `dashboard/src/app/api/chat/route.ts`, `dashboard/src/lib/mcp-client.ts`, `dashboard/src/lib/chat-store.ts`, `dashboard/src/components/chat/*.tsx`
- Modified files: `dashboard/src/components/nav.tsx` (add Chat link), `dashboard/package.json` (new deps), `dashboard/.env.local` (API keys)
- New dependencies: `ai`, `@ai-sdk/react`, `@ai-sdk/anthropic`, `@ai-sdk/openai`, `@ai-sdk/google`, `@ai-sdk/mcp`, `@modelcontextprotocol/sdk`
- No database changes — chat history stored in localStorage
- No MCP server changes — uses existing `leader-mcp` via stdio
