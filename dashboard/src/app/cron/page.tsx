// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import CronCharts from './cron-charts';
import ScheduleList from './schedule-list';
import Link from 'next/link';

export default async function CronPage() {
  let tasks = [];
  let schedules = [];
  let executions = [];

  try {
    const db = await getDb('daas');
    tasks = queryAll(db, 'SELECT * FROM tasks ORDER BY created_at DESC');
    schedules = queryAll(db, 'SELECT * FROM schedules ORDER BY created_at DESC');
    executions = queryAll(db, 'SELECT * FROM executions ORDER BY started_at DESC LIMIT 50');
  } catch {
    // DB not available
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Cron Tasks</h1>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Tasks', value: tasks.length },
          { label: 'Active Schedules', value: schedules.filter((s) => s.enabled).length },
          { label: 'Total Schedules', value: schedules.length },
          { label: 'Recent Executions', value: executions.length },
        ].map((s) => (
          <div key={s.label} className="bg-white border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold">{s.value}</div>
            <div className="text-sm text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* ECharts */}
      <div className="mb-6">
        <CronCharts executions={executions} schedules={schedules} />
      </div>

      {/* Tasks table */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-3">Tasks</h2>
        <div className="border rounded-lg bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Command</th>
                <th className="px-4 py-2">Timeout</th>
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">{t.name}</td>
                  <td className="px-4 py-2 max-w-md truncate font-mono text-xs">{t.command}</td>
                  <td className="px-4 py-2">{t.timeout}s</td>
                  <td className="px-4 py-2">
                    <Link href={`/cron/tasks/${t.id}`} className="text-blue-600 hover:underline text-xs">
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
              {tasks.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">No tasks found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Schedules table with interactive toggle/delete */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Schedules</h2>
        <ScheduleList schedules={schedules} />
      </div>
    </div>
  );
}
