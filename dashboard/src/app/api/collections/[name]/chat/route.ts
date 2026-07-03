// Collection-scoped chat route. Reuses the same streamText + MCP-tools wiring
// as /api/chat, but builds a collection-specific system prompt naming the
// active collection's items (source/form/section/instruction).
//
// The TextStreamChatTransport on the client POSTs `{ messages }` to this URL;
// the collection name is in the URL path (no body shape change).
//
// Tip: set MCP_SERVER=daas-mcp in dashboard/.env.local so the MCP tools
// surfaced to the model are list_sources / search_functions / fetch_data /
// list_collection / list_collections from daas-mcp (matching the collection's
// data sources).

import {
  streamText,
  createUIMessageStreamResponse,
  convertToModelMessages,
  type UIMessage,
} from 'ai';
import { getModel, MissingApiKeyError, type RawProviderConfig } from '@/lib/providers';
import { getMCPTools } from '@/lib/mcp-client';
import { loadCollection } from '@/lib/collections';

export const maxDuration = 120;

interface RouteCtx {
  params: Promise<{ name: string }>;
}

function buildSystemPrompt(coll: { name: string; description: string | null; items: any[] }): string {
  const lines: string[] = [];
  lines.push(`You are a research assistant chatting in the context of a single curated **datasource collection** named "${coll.name}".`);
  if (coll.description) lines.push(`Collection description: ${coll.description}`);
  lines.push('');

  if (coll.items.length === 0) {
    lines.push('This collection is currently EMPTY. Ask the user to add datasources or sections before answering data questions.');
  } else {
    lines.push('The user has curated the following data scope for this chat. Stay within these sources when pulling data:');
    lines.push('');
    for (const it of coll.items) {
      const label = it.source_label || it.source_name;
      const tag = `- **${it.source_name}** (${label})`;
      if (it.section_name) {
        const form = it.form_type ? `${it.form_type} → ` : '';
        lines.push(`${tag} → ${form}${it.section_name}`);
        if (it.instruction) {
          lines.push(`  instruction: ${it.instruction}`);
        }
      } else {
        lines.push(`${tag} (whole datasource)`);
      }
    }
    lines.push('');
    lines.push('Use the available MCP tools (e.g. `fetch_data`, `search_functions`, `list_sources`) to retrieve data, but only against the sources listed above. If the user asks about a source not in this collection, say so and ask whether to broaden scope.');
  }

  lines.push('');
  lines.push('## ECharts Visualization');
  lines.push('When the user asks you to visualize data, output the ECharts configuration as a ```echarts code block. Use standard ECharts option format.');
  lines.push('');
  lines.push('## Guidelines');
  lines.push('- Answer in the user’s language');
  lines.push('- When using tools, briefly explain what you’re doing');
  lines.push('- Format tabular data as Markdown tables when it helps readability');

  return lines.join('\n');
}

function isRawConfig(model: any): model is RawProviderConfig {
  return model?._raw === true;
}

export async function POST(req: Request, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collectionName = decodeURIComponent(name);

  try {
    const coll = await loadCollection(collectionName);
    if (!coll) {
      return new Response(JSON.stringify({ error: `collection '${collectionName}' not found` }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const { messages }: { messages: UIMessage[] } = await req.json();

    let mcpTools: Record<string, any> | undefined;
    try { mcpTools = await getMCPTools(); } catch { /* tools optional */ }

    const model = getModel();
    const systemPrompt = buildSystemPrompt(coll);

    if (isRawConfig(model)) {
      // ponytail: the raw provider path needs SSE wiring we don't duplicate
      // here; recommend using an AI-SDK provider for collection chat.
      return new Response(
        JSON.stringify({ error: 'collection chat requires an AI-SDK provider (anthropic/openai/google). Configure CHAT_PROVIDER accordingly.' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    const result = streamText({
      model,
      system: systemPrompt,
      messages: await convertToModelMessages(messages),
      ...(mcpTools && Object.keys(mcpTools).length > 0 ? { tools: mcpTools } : {}),
    } as any);

    return createUIMessageStreamResponse({
      stream: result.toUIMessageStream({ originalMessages: messages }),
    });
  } catch (error) {
    if (error instanceof MissingApiKeyError) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    const message = error instanceof Error ? error.message : 'Unknown error';
    console.error('Collection chat error:', message);
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
