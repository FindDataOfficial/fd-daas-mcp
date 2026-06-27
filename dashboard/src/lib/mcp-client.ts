import { experimental_createMCPClient } from '@ai-sdk/mcp';
import { Experimental_StdioMCPTransport } from '@ai-sdk/mcp/mcp-stdio';
import path from 'path';

type MCPClient = Awaited<ReturnType<typeof experimental_createMCPClient>>;

let _client: MCPClient | null = null;
let _tools: Record<string, any> | null = null;
let _connecting: Promise<MCPClient> | null = null;
let _lastError: Error | null = null;

const REPO_ROOT = path.resolve(process.cwd(), '..');

function getServerConfig(): { command: string; args: string[]; cwd: string; env?: Record<string, string> } {
  const server = process.env.MCP_SERVER || 'leader-mcp';
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

export async function getMCPClient(): Promise<MCPClient> {
  if (_client) {
    return _client;
  }

  if (_connecting) {
    return _connecting;
  }

  const config = getServerConfig();

  _connecting = (async () => {
    try {
      const transport = new Experimental_StdioMCPTransport({
        command: config.command,
        args: config.args,
        cwd: config.cwd,
        env: config.env,
      });

      _client = await experimental_createMCPClient({ transport });
      _lastError = null;
      return _client;
    } catch (err) {
      _lastError = err instanceof Error ? err : new Error(String(err));
      _connecting = null;
      throw _lastError;
    }
  })();

  return _connecting;
}

export async function getMCPTools(): Promise<Record<string, any>> {
  if (_tools) return _tools;

  const client = await getMCPClient();
  _tools = await client.tools();
  return _tools;
}

export function resetMCPClient(): void {
  if (_client) {
    _client.close().catch(() => {});
  }
  _client = null;
  _tools = null;
  _connecting = null;
  _lastError = null;
}

export function getMCPError(): Error | null {
  return _lastError;
}

export async function checkMCPHealth(): Promise<boolean> {
  try {
    const client = await getMCPClient();
    const tools = await client.tools();
    return Object.keys(tools).length > 0;
  } catch {
    return false;
  }
}

export function getMCPConfig() {
  const config = getServerConfig();
  return {
    server: process.env.MCP_SERVER || 'leader-mcp',
    command: config.command,
    cwd: config.cwd,
  };
}
