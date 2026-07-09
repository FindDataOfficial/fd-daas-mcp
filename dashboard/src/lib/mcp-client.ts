import { experimental_createMCPClient } from '@ai-sdk/mcp';
import { Experimental_StdioMCPTransport } from '@ai-sdk/mcp/mcp-stdio';
import path from 'path';
import { REPO_ROOT } from './paths';

type MCPClient = Awaited<ReturnType<typeof experimental_createMCPClient>>;

interface ServerEntry {
  client: MCPClient | null;
  tools: Record<string, any> | null;
  connecting: Promise<MCPClient> | null;
  lastError: Error | null;
}

// Per-server cache so the dashboard can talk to more than one MCP from a
// single process (e.g. leader-mcp for chat/workflows AND daas-mcp for the
// rules/indicators pages) without resetting each other's connection.
const _servers = new Map<string, ServerEntry>();

function defaultServer(): string {
  // Global default for non-chat callers (workflows API, collections chat,
  // health checks) — these need leader-mcp's tools. The /chat page and
  // /api/chat route default to composite-mcp independently (see chat/page.tsx
  // DEFAULT_SERVER and api/chat/route.ts), so the chat default switch does
  // not ripple to these callers.
  return process.env.MCP_SERVER || 'leader-mcp';
}

function entryFor(server: string): ServerEntry {
  let e = _servers.get(server);
  if (!e) {
    e = { client: null, tools: null, connecting: null, lastError: null };
    _servers.set(server, e);
  }
  return e;
}

export function getServerConfig(server: string): { command: string; args: string[]; cwd: string; env?: Record<string, string> } {
  const serverDir = path.join(REPO_ROOT, 'mcp', server);
  const modelsDir = path.join(REPO_ROOT, 'mcp', 'models');

  // Use fastmcp from the server's venv, matching .mcp.json config
  const fastmcpPath = path.join(serverDir, '.venv', 'bin', 'fastmcp');

  return {
    command: fastmcpPath,
    args: ['run', 'server.py', '--no-banner'],
    cwd: serverDir,
    // ponytail: PYTHONPATH so leader-mcp finds the shared models package
    env: {
      PYTHONPATH: `${modelsDir}:${process.env.PYTHONPATH || ''}`,
      PATH: process.env.PATH || '',
    },
  };
}

export async function getMCPClient(server: string = defaultServer()): Promise<MCPClient> {
  const e = entryFor(server);
  if (e.client) {
    return e.client;
  }

  if (e.connecting) {
    return e.connecting;
  }

  const config = getServerConfig(server);

  e.connecting = (async () => {
    try {
      const transport = new Experimental_StdioMCPTransport({
        command: config.command,
        args: config.args,
        cwd: config.cwd,
        env: config.env,
      });

      e.client = await experimental_createMCPClient({ transport });
      e.lastError = null;
      return e.client;
    } catch (err) {
      e.lastError = err instanceof Error ? err : new Error(String(err));
      e.connecting = null;
      throw e.lastError;
    }
  })();

  return e.connecting;
}

export async function getMCPTools(server: string = defaultServer()): Promise<Record<string, any>> {
  const e = entryFor(server);
  if (e.tools) return e.tools;

  const client = await getMCPClient(server);
  e.tools = await client.tools();
  return e.tools;
}

/**
 * Reset one server's cached client (pass its name) or every cached server
 * (no argument). Existing no-arg callers get the old "reset everything"
 * behavior.
 */
export function resetMCPClient(server?: string): void {
  const resetOne = (s: string) => {
    const e = _servers.get(s);
    if (!e) return;
    if (e.client) {
      e.client.close().catch(() => {});
    }
    _servers.delete(s);
  };
  if (server) {
    resetOne(server);
  } else {
    for (const s of Array.from(_servers.keys())) resetOne(s);
  }
}

export function getMCPError(server: string = defaultServer()): Error | null {
  return entryFor(server).lastError;
}

export async function checkMCPHealth(server: string = defaultServer()): Promise<boolean> {
  try {
    const client = await getMCPClient(server);
    const tools = await client.tools();
    return Object.keys(tools).length > 0;
  } catch {
    return false;
  }
}

export function getMCPConfig(server: string = defaultServer()) {
  const config = getServerConfig(server);
  return {
    server,
    command: config.command,
    cwd: config.cwd,
  };
}

// Raw @modelcontextprotocol/sdk Client path (for composite-mcp). Used for the
// /chat mcp-ui rendering flow where AppRenderer needs a raw client / its
// handlers. Re-exported here so callers import everything from one module.
export {
  getMCPClientRaw,
  getMCPClientRawTools,
  getMCPClientRawError,
  resetMCPClientRaw,
} from './mcp-ui-server';
