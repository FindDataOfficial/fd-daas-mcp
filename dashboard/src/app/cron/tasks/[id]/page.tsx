// @ts-nocheck
import { getDb, queryAll, saveDashboardDb } from '@/lib/db';
import { notFound, redirect } from 'next/navigation';
import Link from 'next/link';
import TaskForm from './task-form';

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ done?: string }>;
}

export default async function EditTaskPage({ params, searchParams }: Props) {
  const { id } = await params;
  const sp = await searchParams;

  if (sp.done === 'deleted') {
    return (
      <div>
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4">
          Task deleted successfully.
        </div>
        <Link href="/cron" className="text-blue-600 hover:underline">← Back to Cron</Link>
      </div>
    );
  }

  const db = await getDb('daas');
  const rows = queryAll(db, 'SELECT * FROM tasks WHERE id = ?', [id]);
  if (!rows.length) notFound();

  const task = rows[0];
  const schedules = queryAll(db, 'SELECT * FROM schedules WHERE task_name = ? ORDER BY name', [task.name]);

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 text-sm text-gray-500">
        <Link href="/cron" className="hover:text-blue-600">Cron</Link>
        <span>/</span>
        <span className="font-medium text-gray-900">Edit Task: {task.name}</span>
      </div>

      <TaskForm task={task} />

      {/* Linked Schedules */}
      <div className="mt-8">
        <h2 className="text-lg font-semibold mb-3">Linked Schedules ({schedules.length})</h2>
        {schedules.length > 0 ? (
          <div className="border rounded-lg bg-white overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-100 text-left">
                <tr>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Cron</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Last Run</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((s) => (
                  <tr key={s.id} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium">{s.name}</td>
                    <td className="px-4 py-2 font-mono text-xs">{s.cron_expr}</td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${s.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'}`}>
                        {s.enabled ? 'Active' : 'Paused'}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500">{s.last_run_at || 'Never'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400">No schedules linked to this task.</p>
        )}
      </div>
    </div>
  );
}
