// @ts-nocheck
import { getMCPTools } from './mcp-client';

/**
 * Extract a JSON payload from an MCP `CallToolResult`. daas-mcp tools return
 * JSON dicts, which FastMCP serializes as a single text content block. Soft
 * errors (e.g. "rule 'x' not found") come back as `{"error": ...}` with
 * `isError=false`, so we check the parsed body too. Mirrors the unwrap helper
 * in the workflows run route.
 */
export function unwrap(result: any): { data?: any; error?: string } {
  if (result == null) return { data: null };
  const textBlock = Array.isArray(result.content)
    ? result.content.find((c: any) => c?.type === 'text')
    : null;
  const text = textBlock?.text ?? (typeof result === 'string' ? result : null);
  if (text != null) {
    try {
      const parsed = JSON.parse(text);
      if (result.isError) {
        return { error: typeof parsed === 'string' ? parsed : parsed?.error || text };
      }
      if (parsed && typeof parsed === 'object' && 'error' in parsed && parsed.error) {
        return { error: String(parsed.error) };
      }
      return { data: parsed };
    } catch {
      return result.isError ? { error: text } : { data: text };
    }
  }
  if (result.isError) return { error: result.error || 'tool error' };
  if (result && typeof result === 'object' && 'error' in result && result.error) {
    return { error: String(result.error) };
  }
  return { data: result };
}

/**
 * Call a tool on the given MCP server and return unwrapped data. Throws an
 * Error with a clear message if the server is unavailable, the tool is missing,
 * or the tool returns an `isError`/`{error}` payload.
 */
export async function callTool(
  server: string,
  toolName: string,
  args: Record<string, any> = {},
): Promise<any> {
  const tools = await getMCPTools(server);
  const tool = tools[toolName];
  if (!tool || typeof tool.execute !== 'function') {
    throw new Error(`tool '${toolName}' not exposed by ${server}`);
  }
  const raw = await tool.execute(args);
  const { data, error } = unwrap(raw);
  if (error) throw new Error(error);
  return data;
}
