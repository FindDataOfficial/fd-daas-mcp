import {
  streamText,
  createUIMessageStreamResponse,
  convertToModelMessages,
  stepCountIs,
  type UIMessage,
} from 'ai';
import { getModel, MissingApiKeyError, type RawProviderConfig } from '@/lib/providers';
import { getMCPTools, getMCPClientRawTools } from '@/lib/mcp-client';

export const maxDuration = 120;

const SYSTEM_PROMPT = `You are a helpful AI assistant with access to MCP (Model Context Protocol) tools for data querying and analysis.

## ECharts Visualization
When the user asks you to visualize data or create a chart, output the ECharts configuration as a \`\`\`echarts code block. Use standard ECharts option format.

Example:
\`\`\`echarts
{
  "title": { "text": "Sample Chart" },
  "xAxis": { "type": "category", "data": ["A", "B", "C"] },
  "yAxis": { "type": "value" },
  "series": [{ "data": [1, 2, 3], "type": "bar" }]
}
\`\`\`

## Guidelines
- Answer in the user's language
- When using tools, explain what you're doing
- Format data clearly with tables when appropriate`;

// Simple SSE encoder for raw fetch path
function sse(data: unknown): string {
  return `data: ${JSON.stringify(data)}\n\n`;
}

function randomId(): string {
  return `msg-${Math.random().toString(36).slice(2, 10)}`;
}

/** Raw OpenAI-compatible streaming for providers that don't work with AI SDK */
async function rawStreamResponse(
  config: RawProviderConfig,
  messages: UIMessage[],
  mcpTools: Record<string, any> | undefined,
) {
  const apiMessages: Array<{ role: string; content: string }> = [
    { role: 'system', content: SYSTEM_PROMPT },
  ];

  for (const msg of messages) {
    const content = msg.parts
      .filter((p: any) => p.type === 'text')
      .map((p: any) => p.text)
      .join('\n');
    if (content) {
      apiMessages.push({ role: msg.role === 'user' ? 'user' : 'assistant', content });
    }
  }

  const encoder = new TextEncoder();
  return new ReadableStream({
    async start(controller) {
      const msgId = randomId();
      controller.enqueue(encoder.encode(sse({ type: 'text-start', id: msgId })));

      try {
        const url = `${config.baseURL}/chat/completions`;
        const body: any = { model: config.model, messages: apiMessages, stream: true };

        if (mcpTools && Object.keys(mcpTools).length > 0) {
          body.tools = Object.values(mcpTools).map((t: any) => ({
            type: 'function',
            function: {
              name: t.name || 'tool',
              description: t.description || '',
              parameters: t.parameters || t.inputSchema || { type: 'object', properties: {} },
            },
          }));
        }

        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${config.apiKey}`,
          },
          body: JSON.stringify(body),
        });

        if (!response.ok) {
          const err = await response.text();
          controller.enqueue(encoder.encode(sse({ type: 'error', errorText: `API ${response.status}: ${err.slice(0, 200)}` })));
          controller.enqueue(encoder.encode(sse({ type: 'text-end', id: msgId })));
          controller.enqueue(encoder.encode('data: [DONE]\n\n'));
          controller.close();
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) { controller.close(); return; }

        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith('data: ')) continue;
            const data = trimmed.slice(6);
            if (data === '[DONE]') continue;
            try {
              const parsed = JSON.parse(data);
              const delta = parsed.choices?.[0]?.delta;
              if (delta?.content) {
                controller.enqueue(encoder.encode(sse({
                  type: 'text-delta', id: msgId, textDelta: delta.content,
                })));
              }
            } catch { /* skip */ }
          }
        }
      } catch (err: any) {
        controller.enqueue(encoder.encode(sse({ type: 'error', errorText: err.message || 'Stream error' })));
      }
      controller.enqueue(encoder.encode(sse({ type: 'text-end', id: msgId })));
      controller.enqueue(encoder.encode('data: [DONE]\n\n'));
      controller.close();
    },
  });
}

function isRawConfig(model: any): model is RawProviderConfig {
  return model?._raw === true;
}

export async function POST(req: Request) {
  try {
    const { messages, server }: { messages: UIMessage[]; server?: string } = await req.json();

    // Resolve the MCP server for this chat session. Default is composite-mcp
    // (see mcp-client.ts defaultServer()); the /chat selector sends `server`
    // explicitly so the user can pick leader-mcp etc.
    const mcpServer = server || process.env.MCP_SERVER || 'composite-mcp';
    const useRawClient = mcpServer === 'composite-mcp';

    // Load MCP tools (optional). composite-mcp uses the raw SDK Client so the
    // same client can back the /api/mcp-ui/* AppRenderer handlers and so
    // _meta.ui.resourceUri survives in tool results. Other servers use
    // @ai-sdk/mcp unchanged.
    let mcpTools: Record<string, any> | undefined;
    try {
      mcpTools = useRawClient
        ? await getMCPClientRawTools(mcpServer)
        : await getMCPTools(mcpServer);
    } catch {
      /* unavailable */
    }

    const model = getModel();

    // Raw fetch path for volcengine/openrouter/ollama
    if (isRawConfig(model)) {
      const stream = await rawStreamResponse(model, messages, mcpTools);
      return new Response(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    }

    // AI SDK path for anthropic/openai/google
    const result = streamText({
      model,
      system: SYSTEM_PROMPT,
      messages: await convertToModelMessages(messages),
      ...(mcpTools && Object.keys(mcpTools).length > 0 ? { tools: mcpTools } : {}),
      // ai@5 renamed maxSteps -> stopWhen(stepCountIs(n))
      stopWhen: stepCountIs(10),
    });

    return createUIMessageStreamResponse({
      stream: result.toUIMessageStream({ originalMessages: messages }),
    });
  } catch (error) {
    if (error instanceof MissingApiKeyError) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 401, headers: { 'Content-Type': 'application/json' },
      });
    }
    const message = error instanceof Error ? error.message : 'Unknown error';
    console.error('Chat API error:', message);
    return new Response(JSON.stringify({ error: message }), {
      status: 500, headers: { 'Content-Type': 'application/json' },
    });
  }
}
