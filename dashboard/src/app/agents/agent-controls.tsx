// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Props {
  agentName: string;
}

/** Delete button for the agent detail page. DELETEs `/api/agents/[name]`;
 *  on success redirects to `/agents`, on refusal (e.g. the agent is still
 *  referenced by a workflow step) surfaces the leader-mcp error inline. */
export default function AgentControls({ agentName }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function handleDelete() {
    if (!confirm(`Delete agent "${agentName}"?`)) return;
    setBusy(true);
    setError('');
    try {
      const res = await fetch(`/api/agents/${encodeURIComponent(agentName)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        router.push('/agents');
        router.refresh();
      } else {
        const data = await res.json().catch(() => ({ error: 'Request failed' }));
        setError(data.error || `Failed (${res.status})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Network error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Link
        href={`/agents/${encodeURIComponent(agentName)}/edit`}
        className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded"
      >
        Edit
      </Link>
      <button
        onClick={handleDelete}
        disabled={busy}
        className="text-sm bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 rounded disabled:opacity-50"
      >
        {busy ? 'Deleting…' : 'Delete'}
      </button>
      {error && (
        <span className="text-xs text-red-600 max-w-md">{error}</span>
      )}
    </div>
  );
}
