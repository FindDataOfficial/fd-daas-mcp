// @ts-nocheck
import { NextRequest, NextResponse } from 'next/server';
import { getMCPTools } from '@/lib/mcp-client';
import { invalidateDb } from '@/lib/db';

export const maxDuration = 120;

interface RouteCtx {
  params: Promise<{ name: string }>;
}

/**
 * Extract a JSON payload from an MCP `CallToolResult`. leader-mcp tools return
 * JSON dicts, which FastMCP serializes as a single text content block. Soft
 * errors (e.g. "workflow 'x' not found") come back as `{"error": ...}` with
 * `isError=false`, so we check the parsed body too.
 */
function unwrap(result: any): { data?: any; error?: string } {
  if (result == null) return { data: null };
  // CallToolResult shape: { content: [{ type: 'text', text }], isError, ... }
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
  // Already a plain object (some wrappers unwrap).
  if (result.isError) return { error: result.error || 'tool error' };
  if (result && typeof result === 'object' && 'error' in result && result.error) {
    return { error: String(result.error) };
  }
  return { data: result };
}

export async function POST(req: NextRequest, ctx: RouteCtx) {
  const { name: rawName } = await ctx.params;
  const name = decodeURIComponent(rawName);

  let body: any;
  try {
    body = await req.json();
  } catch {
    body = {};
  }
  const mode = body?.mode === 'step' ? 'step' : 'all';
  const stepSortOrder = Number(body?.step_sort_order);

  if (mode === 'step' && !Number.isFinite(stepSortOrder)) {
    return NextResponse.json({ error: 'step_sort_order is required for mode=step' }, { status: 400 });
  }

  let tools: Record<string, any>;
  try {
    tools = await getMCPTools();
  } catch (e: any) {
    return NextResponse.json(
      { error: `leader-mcp unavailable: ${e?.message ?? String(e)}` },
      { status: 502 },
    );
  }

  const toolName = mode === 'step' ? 'run_workflow_step' : 'run_workflow';
  const tool = tools[toolName];
  if (!tool || typeof tool.execute !== 'function') {
    return NextResponse.json(
      { error: `tool '${toolName}' not exposed by leader-mcp` },
      { status: 502 },
    );
  }

  const args =
    mode === 'step' ? { name, step_sort_order: stepSortOrder } : { name };

  try {
    const raw = await tool.execute(args);
    const { data, error } = unwrap(raw);
    if (error) {
      return NextResponse.json({ error }, { status: 400 });
    }
    // The run wrote rows via leader-mcp (a separate process); drop the cached
    // sql.js handle so the next page render re-reads the file.
    invalidateDb('daas');
    return NextResponse.json({ ok: true, result: data });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message ?? String(e) },
      { status: 500 },
    );
  }
}
