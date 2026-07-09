// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';

export default async function WorkflowsPage() {
  let workflows: any[] = [];
  let stats = { total_workflows: 0, total_runs: 0, active_runs: 0 };

  try {
    const db = await getDb('daas');
    // Each workflow + its step count + its most-recent-run status/started_at,
    // via correlated subqueries (avoids a separate round-trip per row).
    workflows = queryAll(
      db,
      `SELECT
         w.id, w.name, w.description, w.created_at,
         (SELECT COUNT(*) FROM workflow_steps s WHERE s.workflow_id = w.id) AS step_count,
         (SELECT r.status FROM workflow_runs r
            WHERE r.workflow_id = w.id
            ORDER BY r.started_at DESC, r.id DESC LIMIT 1) AS last_run_status,
         (SELECT r.started_at FROM workflow_runs r
            WHERE r.workflow_id = w.id
            ORDER BY r.started_at DESC, r.id DESC LIMIT 1) AS last_run_at
       FROM workflows w
       ORDER BY w.created_at DESC`,
    );
    const s = queryAll(
      db,
      `SELECT
         (SELECT COUNT(*) FROM workflows) AS total_workflows,
         (SELECT COUNT(*) FROM workflow_runs) AS total_runs,
         (SELECT COUNT(*) FROM workflow_runs WHERE status IN ('running','in_progress')) AS active_runs`,
    );
    if (s[0]) stats = s[0];
  } catch {
    // DB not available
  }

  const statusBadge = (status: string | null) => {
    if (!status) return <span className="text-xs text-gray-400">No runs yet</span>;
    const map: Record<string, string> = {
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      running: 'bg-blue-100 text-blue-800',
      in_progress: 'bg-yellow-100 text-yellow-800',
    };
    return (
      <span className={`text-xs px-2 py-0.5 rounded ${map[status] || 'bg-gray-100 text-gray-600'}`}>
        {status}
      </span>
    );
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Workflows</h1>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Workflows', value: stats.total_workflows },
          { label: 'Total Runs', value: stats.total_runs },
          { label: 'Active Runs', value: stats.active_runs },
        ].map((s) => (
          <div key={s.label} className="bg-white border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold">{s.value}</div>
            <div className="text-sm text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Workflows table */}
      <div className="border rounded-lg bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Description</th>
              <th className="px-4 py-2">Steps</th>
              <th className="px-4 py-2">Last Run</th>
              <th className="px-4 py-2">Last Run At</th>
              <th className="px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {workflows.map((w) => (
              <tr key={w.id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">{w.name}</td>
                <td className="px-4 py-2 max-w-md truncate text-gray-600">{w.description || '—'}</td>
                <td className="px-4 py-2">{w.step_count}</td>
                <td className="px-4 py-2">{statusBadge(w.last_run_status)}</td>
                <td className="px-4 py-2 text-xs text-gray-500">{w.last_run_at || '—'}</td>
                <td className="px-4 py-2">
                  <Link href={`/workflows/${encodeURIComponent(w.name)}`} className="text-blue-600 hover:underline text-xs">
                    View
                  </Link>
                </td>
              </tr>
            ))}
            {workflows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">No workflows yet</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
