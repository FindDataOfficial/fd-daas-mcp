// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import OutputBlock from './output-block';

interface PageProps {
  params: Promise<{ name: string; runId: string }>;
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

function safeParse(s: string | null | undefined): any {
  if (s == null || s === '') return null;
  try {
    return JSON.parse(s);
  } catch {
    return s;
  }
}

function MetaBadge({ meta }: { meta: any }) {
  if (!meta || typeof meta !== 'object') return null;
  const parts: string[] = [];
  if (meta.fallback) parts.push(`fallback: ${meta.fallback}`);
  if (meta.reason) parts.push(meta.reason);
  if (meta._truncated) parts.push('output truncated');
  // Surface any other keys generically.
  for (const k of Object.keys(meta)) {
    if (!['fallback', 'reason', '_truncated'].includes(k)) {
      parts.push(`${k}: ${typeof meta[k] === 'string' ? meta[k] : JSON.stringify(meta[k])}`);
    }
  }
  if (parts.length === 0) return null;
  return (
    <span className="text-xs px-2 py-0.5 rounded bg-yellow-50 text-yellow-800 border border-yellow-200 ml-2">
      {parts.join(' · ')}
    </span>
  );
}

export default async function RunDetailPage({ params }: PageProps) {
  const { name: rawName, runId: rawRunId } = await params;
  const name = decodeURIComponent(rawName);
  const runId = Number(rawRunId);

  let run: any = null;
  let results: any[] = [];

  try {
    const db = await getDb('daas');
    if (Number.isFinite(runId)) {
      const runRows = queryAll(
        db,
        `SELECT r.*, w.name AS workflow_name
         FROM workflow_runs r
         JOIN workflows w ON w.id = r.workflow_id
         WHERE w.name = ? AND r.id = ?
         LIMIT 1`,
        [name, runId],
      );
      run = runRows[0] || null;
      if (run) {
        results = queryAll(
          db,
          'SELECT * FROM workflow_step_results WHERE run_id = ? ORDER BY step_sort_order',
          [run.id],
        );
      }
    }
  } catch {
    // DB not available
  }

  if (!run) {
    return (
      <div>
        <Link
          href={`/workflows/${encodeURIComponent(name)}`}
          className="text-blue-600 hover:underline text-sm mb-4 inline-block"
        >
          ← Back to {name}
        </Link>
        <h1 className="text-2xl font-bold mb-2">Run not found</h1>
        <p className="text-gray-500 text-sm">
          No run <code className="bg-gray-100 px-1 rounded">#{runId}</code> exists for workflow{' '}
          <code className="bg-gray-100 px-1 rounded">{name}</code>.
        </p>
      </div>
    );
  }

  return (
    <div>
      <Link
        href={`/workflows/${encodeURIComponent(name)}`}
        className="text-blue-600 hover:underline text-sm mb-4 inline-block"
      >
        ← Back to {name}
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-3">
          Run #{run.id} <span>{statusBadge(run.status)}</span>
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          started {run.started_at || '—'} · finished {run.finished_at || '—'}
        </p>
      </div>

      {/* Step results */}
      <div className="space-y-4">
        {results.map((r) => {
          const meta = safeParse(r.meta_json);
          const output = safeParse(r.output_json);
          return (
            <div key={r.id} className="border rounded-lg bg-white p-4">
              <div className="flex items-center gap-3 mb-2">
                <span className="font-medium">Step {r.step_sort_order}</span>
                {statusBadge(r.status)}
                <span className="text-xs text-gray-400">ran {r.ran_at || '—'}</span>
                <MetaBadge meta={meta} />
              </div>
              {r.error && (
                <pre className="text-xs bg-red-50 border border-red-200 text-red-800 rounded p-2 mb-2 whitespace-pre-wrap break-all">
                  {r.error}
                </pre>
              )}
              <OutputBlock output={output} />
            </div>
          );
        })}
        {results.length === 0 && (
          <div className="border rounded-lg bg-white p-8 text-center text-gray-400">
            No step results for this run
          </div>
        )}
      </div>
    </div>
  );
}
