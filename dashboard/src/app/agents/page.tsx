// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import EnabledToggle from './enabled-toggle';

export default async function AgentsPage() {
  let agents: any[] = [];
  let upstreamSet = new Set<string>();

  try {
    const db = await getDb('daas');
    agents = queryAll(
      db,
      `SELECT id, name, upstream, role, goal, model, enabled, created_at, updated_at
       FROM specialist_agents
       ORDER BY name ASC`,
    );
    const ups = queryAll(db, 'SELECT name FROM leader_upstreams');
    upstreamSet = new Set(ups.map((u: any) => u.name));
  } catch {
    // DB / table not available — render empty state
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Specialist Agents</h1>
        <Link
          href="/agents/new"
          className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded"
        >
          New agent
        </Link>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        CrewAI specialist agents (<code>specialist_agents</code>) — each bound to one data-fetch MCP
        upstream and used by data workflows.
      </p>

      <div className="border rounded-lg bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Upstream</th>
              <th className="px-4 py-2">Model</th>
              <th className="px-4 py-2">Enabled</th>
              <th className="px-4 py-2">Updated</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => {
              const missing = !upstreamSet.has(a.upstream);
              return (
                <tr key={a.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">
                    <Link
                      href={`/agents/${encodeURIComponent(a.name)}`}
                      className="text-blue-600 hover:underline"
                    >
                      {a.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {a.upstream}
                    {missing && (
                      <span
                        className="ml-2 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700"
                        title="This upstream is no longer present in leader_upstreams"
                      >
                        missing
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-600">
                    {a.model || <span className="italic text-gray-400">default (shared LLM)</span>}
                  </td>
                  <td className="px-4 py-2">
                    <EnabledToggle name={a.name} enabled={!!a.enabled} />
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">{a.updated_at || a.created_at || '—'}</td>
                </tr>
              );
            })}
            {agents.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  No agents yet — click <span className="text-blue-600">New agent</span> to create one,
                  or run <code>seed_specialist_agents.py</code>.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
