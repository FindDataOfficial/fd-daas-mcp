// Same-origin proxy from the browser to the server-side raw MCP Client.
// AppRenderer runs in the browser (sandboxed iframe) but needs to drive the
// stdio MCP process that lives on the Next.js server. The browser handlers
// (ui-resource-block.tsx) call these routes, which forward to the raw Client
// for the selected server. Same-origin by construction (dashboard only).
import { NextResponse } from 'next/server';
import { getMCPClientRaw } from '@/lib/mcp-ui-server';

export const dynamic = 'force-dynamic';

type Body = {
  server?: string;
  uri?: string;
  name?: string;
  arguments?: Record<string, unknown>;
};

export async function POST(
  req: Request,
  { params }: { params: Promise<{ op: string }> },
) {
  const { op } = await params;
  const body = (await req.json().catch(() => ({}))) as Body;
  const server = body.server;
  if (!server) {
    return NextResponse.json({ error: 'server required' }, { status: 400 });
  }

  try {
    const client = await getMCPClientRaw(server);
    switch (op) {
      case 'read-resource': {
        if (!body.uri) {
          return NextResponse.json({ error: 'uri required' }, { status: 400 });
        }
        const res = await client.readResource({ uri: body.uri });
        return NextResponse.json(res);
      }
      case 'call-tool': {
        if (!body.name) {
          return NextResponse.json({ error: 'name required' }, { status: 400 });
        }
        const res = await client.callTool({
          name: body.name,
          arguments: body.arguments ?? {},
        });
        return NextResponse.json(res);
      }
      case 'list-resources': {
        const res = await client.listResources();
        return NextResponse.json(res);
      }
      default:
        return NextResponse.json({ error: `unknown op: ${op}` }, { status: 404 });
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`mcp-ui/${op} error:`, message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export function GET() {
  return NextResponse.json({ error: 'POST only' }, { status: 405 });
}
