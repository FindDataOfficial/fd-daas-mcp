// Server-side raw @modelcontextprotocol/sdk Client singleton, used for the
// composite-mcp chat path. Unlike @ai-sdk/mcp's client, the raw Client can be
// passed (or its handlers proxied) to @mcp-ui/client's AppRenderer, which is
// what renders MCP-Apps UI resources inline in /chat.
//
// Why a separate client from mcp-client.ts: @ai-sdk/mcp's
// experimental_createMCPClient does not expose the underlying raw SDK Client
// that AppRenderer needs. For composite-mcp we use this raw client for BOTH
// tool-calling (mapped to AI-SDK tools) and the /api/mcp-ui/* handler proxy.
// Other servers keep the @ai-sdk/mcp path unchanged.

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { tool, jsonSchema } from 'ai';
import { getServerConfig } from './mcp-client';

interface RawEntry {
  client: Client | null;
  connecting: Promise<Client> | null;
  lastError: Error | null;
}

const _raw = new Map<string, RawEntry>();

function entryFor(server: string): RawEntry {
  let e = _raw.get(server);
  if (!e) {
    e = { client: null, connecting: null, lastError: null };
    _raw.set(server, e);
  }
  return e;
}

/** Return the raw SDK Client for `server` (singleton; spawned once per process). */
export async function getMCPClientRaw(server: string): Promise<Client> {
  const e = entryFor(server);
  if (e.client) return e.client;
  if (e.connecting) return e.connecting;

  const config = getServerConfig(server);

  e.connecting = (async () => {
    try {
      const transport = new StdioClientTransport({
        command: config.command,
        args: config.args,
        cwd: config.cwd,
        env: { ...process.env, ...(config.env || {}) } as Record<string, string>,
      });
      const client = new Client(
        { name: 'mcp-dashboard-raw', version: '1.0.0' },
        { capabilities: {} },
      );
      await client.connect(transport);
      e.client = client;
      e.lastError = null;
      return client;
    } catch (err) {
      e.lastError = err instanceof Error ? err : new Error(String(err));
      e.connecting = null;
      throw e.lastError;
    }
  })();

  return e.connecting;
}

/**
 * Map the raw client's tool list to AI-SDK-shaped tools for streamText.
 * Mirrors @ai-sdk/mcp: tool() + jsonSchema(inputSchema). The execute return
 * value is the full CallToolResult so _meta.ui.resourceUri survives intact
 * for the chat UI to detect and render via AppRenderer.
 */
export async function getMCPClientRawTools(
  server: string,
): Promise<Record<string, any>> {
  const client = await getMCPClientRaw(server);
  const { tools } = await client.listTools();
  const out: Record<string, any> = {};

  for (const t of tools) {
    const name = t.name;
    const rawSchema = (t.inputSchema ?? {
      type: 'object',
      properties: {},
    }) as Record<string, unknown>;
    // ponytail: the MCP inputSchema is already a JSON Schema; jsonSchema()
    // wraps it so streamText accepts it (mirrors @ai-sdk/mcp). Casts satisfy
    // FlexibleSchema<INPUT> inference without importing JSONSchema7.
    const inputSchema = jsonSchema({
      ...rawSchema,
      properties: (rawSchema.properties as Record<string, unknown>) ?? {},
      additionalProperties: false,
    }) as never;
    out[name] = tool({
      description: t.description ?? '',
      inputSchema,
      execute: async (args: Record<string, unknown>) => {
        const res = await client.callTool({ name, arguments: args });
        return res;
      },
    });
  }

  return out;
}

export function getMCPClientRawError(server: string): Error | null {
  return entryFor(server).lastError;
}

/** Close + drop one server's raw client (or all when called with no arg). */
export function resetMCPClientRaw(server?: string): void {
  const resetOne = (s: string) => {
    const e = _raw.get(s);
    if (!e) return;
    if (e.client) {
      e.client.close().catch(() => {});
    }
    _raw.delete(s);
  };
  if (server) {
    resetOne(server);
  } else {
    for (const s of Array.from(_raw.keys())) resetOne(s);
  }
}
