// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import AgentForm from '../../agent-form';
import { getAgentOptions } from '../../server-data';

interface PageProps {
  params: Promise<{ name: string }>;
}

export default async function EditAgentPage({ params }: PageProps) {
  const { name: rawName } = await params;
  const name = decodeURIComponent(rawName);

  const options = await getAgentOptions();

  let agent: any = null;
  try {
    const db = await getDb('daas');
    const rows = queryAll(
      db,
      `SELECT id, name, upstream, role, goal, backstory, model, enabled
       FROM specialist_agents
       WHERE name = ?
       LIMIT 1`,
      [name],
    );
    agent = rows[0] || null;
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

  const initial = {
    name: agent.name,
    upstream: agent.upstream,
    role: agent.role || '',
    goal: agent.goal || '',
    backstory: agent.backstory || '',
    model: agent.model || '',
    enabled: agent.enabled !== false,
  };

  return (
    <div>
      <Link
        href={`/agents/${encodeURIComponent(agent.name)}`}
        className="text-blue-600 hover:underline text-sm mb-4 inline-block"
      >
        ← Back to agent
      </Link>
      <h1 className="text-2xl font-bold mb-6">Edit agent</h1>
      <AgentForm mode="edit" initial={initial} options={options} />
    </div>
  );
}
