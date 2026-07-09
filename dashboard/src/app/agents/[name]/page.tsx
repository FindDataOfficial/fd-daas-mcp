// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import AgentControls from '../agent-controls';

interface PageProps {
  params: Promise<{ name: string }>;
}

export default async function AgentDetailPage({ params }: PageProps) {
  const { name: rawName } = await params;
  const name = decodeURIComponent(rawName);

  let agent: any = null;
  let upstreamMissing = false;

  try {
    const db = await getDb('daas');
    const rows = queryAll(
      db,
      `SELECT id, name, upstream, role, goal, backstory, model, enabled, created_at, updated_at
       FROM specialist_agents
       WHERE name = ?
       LIMIT 1`,
      [name],
    );
    agent = rows[0] || null;
    if (agent) {
      const ups = queryAll(db, 'SELECT name FROM leader_upstreams');
      const upstreamSet = new Set(ups.map((u: any) => u.name));
      upstreamMissing = !upstreamSet.has(agent.upstream);
    }
  } catch {
    // DB / table not available — render not-found
  }

  if (!agent) {
    return (
      <div>
        <Link href="/agents" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
          ← Back to agents
        </Link>
        <h1 className="text-2xl font-bold mb-2">Agent not found</h1>
        <p className="text-sm text-gray-500">
          No specialist agent named <code>{name}</code> exists.
        </p>
      </div>
    );
  }

  const Field = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div className="grid grid-cols-3 gap-2 py-2 border-t first:border-t-0">
      <div className="text-sm font-medium text-gray-500">{label}</div>
      <div className="col-span-2 text-sm break-words">{value}</div>
    </div>
  );

  return (
    <div>
      <Link href="/agents" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to agents
      </Link>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold font-mono">{agent.name}</h1>
        <AgentControls agentName={agent.name} />
      </div>

      <div className="bg-white border rounded-lg p-4 max-w-3xl">
        <Field label="Name" value={<span className="font-mono">{agent.name}</span>} />
        <Field
          label="Upstream"
          value={
            <span className="font-mono">
              {agent.upstream}
              {upstreamMissing && (
                <span
                  className="ml-2 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700"
                  title="This upstream is no longer present in leader_upstreams"
                >
                  missing
                </span>
              )}
            </span>
          }
        />
        <Field
          label="Model"
          value={
            agent.model || <span className="italic text-gray-400">default (shared LLM)</span>
          }
        />
        <Field label="Role" value={agent.role} />
        <Field label="Goal" value={agent.goal} />
        <Field label="Backstory" value={agent.backstory || <span className="text-gray-400">—</span>} />
        <Field
          label="Enabled"
          value={
            <span
              className={`text-xs px-2 py-0.5 rounded ${
                agent.enabled
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-500'
              }`}
            >
              {agent.enabled ? 'on' : 'off'}
            </span>
          }
        />
        <Field label="Created" value={<span className="text-gray-500 text-xs">{agent.created_at || '—'}</span>} />
        <Field label="Updated" value={<span className="text-gray-500 text-xs">{agent.updated_at || '—'}</span>} />
      </div>
    </div>
  );
}
