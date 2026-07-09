'use client';

// Renders one MCP-Apps UI tool result inline using @mcp-ui/client's AppRenderer.
// AppRenderer runs in the browser (sandboxed iframe + postMessage); it drives
// the server-side raw MCP Client (which owns the stdio process) via the
// same-origin /api/mcp-ui/* proxy routes. We pass NO `client` prop and instead
// supply onReadResource/onCallTool/onListResources handlers that fetch the
// proxy — per @mcp-ui/client v7.1.1, `toolResourceUri + onReadResource` is the
// supported no-client mode.

import { useEffect, useState } from 'react';
import { AppRenderer } from '@mcp-ui/client';

interface Props {
  /** MCP server the chat is talking to (drives the /api/mcp-ui/* proxy). */
  server: string;
  toolName: string;
  toolResourceUri: string;
  toolInput?: Record<string, unknown>;
  toolResult?: unknown;
}

interface SandboxConfig {
  url: URL;
}

async function postOp(op: string, body: Record<string, unknown>) {
  const res = await fetch(`/api/mcp-ui/${op}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `request failed: ${res.status}`);
  }
  return res.json();
}

export default function UiResourceBlock({
  server,
  toolName,
  toolResourceUri,
  toolInput,
  toolResult,
}: Props) {
  // AppRenderer needs a URL to the sandbox proxy page; defer to the browser
  // (window is unavailable during SSR).
  const [sandbox, setSandbox] = useState<SandboxConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSandbox({
      url: new URL('/mcp-ui-sandbox-proxy.html', window.location.origin),
    });
  }, []);

  if (error) {
    return (
      <div className="border rounded-lg bg-red-50 my-2 p-3 text-sm text-red-700">
        Failed to render UI for <code className="font-mono">{toolName}</code>: {error}
      </div>
    );
  }

  if (!sandbox) {
    return (
      <div className="border rounded-lg bg-gray-50 my-2 p-3 text-sm text-gray-400">
        Loading widget…
      </div>
    );
  }

  return (
    <div className="border rounded-lg bg-white my-2 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border-b">
        <span className="text-xs">🖼️</span>
        <code className="text-xs font-mono text-gray-700">{toolName}</code>
        <span className="text-xs text-gray-400 ml-auto">MCP-Apps UI</span>
      </div>
      <div style={{ minHeight: 320 }}>
        <AppRenderer
          toolName={toolName}
          toolResourceUri={toolResourceUri}
          toolInput={toolInput}
          toolResult={toolResult as never}
          sandbox={sandbox}
          hostInfo={{ name: 'cli-anything-dashboard', version: '1.0.0' }}
          onOpenLink={async (params: any) => {
            if (params?.url) {
              window.open(params.url, '_blank', 'noopener');
            }
            return {};
          }}
          onReadResource={async (params: any) =>
            postOp('read-resource', { server, uri: params.uri })
          }
          onCallTool={async (params: any) =>
            postOp('call-tool', {
              server,
              name: params.name,
              arguments: params.arguments ?? {},
            })
          }
          onListResources={async () => postOp('list-resources', { server })}
          onError={(err: Error) => setError(err.message)}
        />
      </div>
    </div>
  );
}
