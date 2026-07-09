// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import RunControls from './run-controls';

interface PageProps {
  params: Promise<{ name: string }>;
}

const STATUS_BADGE: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  running: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-yellow-100 text-yellow-800',
};

function statusBadge(status: string) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  );
}

export default async function WorkflowDetailPage({ params }: PageProps) {
  const { name: rawName } = await params;
  const name = decodeURIComponent(rawName);

  let workflow: any = null;
  let steps: any[] = [];
  let runs: any[] = [];

  try {
    const db = await getDb('daas');
    const wfRows = queryAll(db, 'SELECT * FROM workflows WHERE name = ? LIMIT 1', [name]);
    workflow = wfRows[0] || null;
    if (workflow) {
      steps = queryAll(
        db,
        'SELECT * FROM workflow_steps WHERE workflow_id = ? ORDER BY sort_order',
        [workflow.id],
      );
      runs = queryAll(
        db,
        'SELECT * FROM workflow_runs WHERE workflow_id = ? ORDER BY started_at DESC, id DESC LIMIT 20',
        [workflow.id],
      );
    }
  } catch {
    // DB not available
  }

  if (!workflow) {
    return (
      <div>
        <Link href="/workflows" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
          ← Back to workflows
        </Link>
        <h1 className="text-2xl font-bold mb-2">Workflow not found</h1>
        <p className="text-gray-500 text-sm">
          No workflow named <code className="bg-gray-100 px-1 rounded">{name}</code> exists in <code>mcp/daas.db</code>.
        </p>
      </div>
    );
  }

  return (
    <div>
      <Link href="/workflows" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to workflows
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{workflow.name}</h1>
          {workflow.description && (
            <p className="text-gray-600 text-sm mt-1 max-w-3xl">{workflow.description}</p>
          )}
          <p className="text-xs text-gray-400 mt-1">created {workflow.created_at}</p>
        </div>
        <RunControls workflowName={workflow.name} />
      </div>

      {/* Steps */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-3">Steps ({steps.length})</h2>
        <div className="border rounded-lg bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="px-4 py-2 w-12">#</th>
                <th className="px-4 py-2">Agent</th>
                <th className="px-4 py-2">Request</th>
                <th className="px-4 py-2">Depends On</th>
                <th className="px-4 py-2">On Fail</th>
                <th className="px-4 py-2">Model</th>
                <th className="px-4 py-2">Enabled</th>
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((s) => (
                <tr key={s.id} className="border-t align-top hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">{s.sort_order}</td>
                  <td className="px-4 py-2 font-mono text-xs">{s.agent}</td>
                  <td className="px-4 py-2 max-w-md text-gray-700">{s.request}</td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {s.depends_on ? s.depends_on : '—'}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${s.on_fail === 'stop' ? 'bg-red-50 text-red-700' : 'bg-gray-50 text-gray-600'}`}>
                      {s.on_fail}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {s.model ? s.model : <span className="italic text-gray-400">default: fast</span>}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${s.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'}`}>
                      {s.enabled ? 'on' : 'off'}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <RunControls workflowName={workflow.name} stepSortOrder={s.sort_order} />
                  </td>
                </tr>
              ))}
              {steps.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-400">No steps defined</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent runs */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Recent Runs</h2>
        <div className="border rounded-lg bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="px-4 py-2">Run ID</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Started</th>
                <th className="px-4 py-2">Finished</th>
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs">{r.id}</td>
                  <td className="px-4 py-2">{statusBadge(r.status)}</td>
                  <td className="px-4 py-2 text-xs text-gray-500">{r.started_at || '—'}</td>
                  <td className="px-4 py-2 text-xs text-gray-500">{r.finished_at || '—'}</td>
                  <td className="px-4 py-2">
                    <Link
                      href={`/workflows/${encodeURIComponent(workflow.name)}/runs/${r.id}`}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-400">No runs yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
