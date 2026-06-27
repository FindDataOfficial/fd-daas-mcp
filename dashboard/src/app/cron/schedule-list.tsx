'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface Props {
  schedules: Array<{
    id: string;
    name: string;
    task_name: string;
    cron_expr: string;
    enabled: number;
    last_run_at?: string;
  }>;
}

export default function ScheduleList({ schedules }: Props) {
  const router = useRouter();
  const [items, setItems] = useState(schedules);
  const [message, setMessage] = useState('');

  async function toggle(scheduleId: string, currentEnabled: number) {
    setMessage('');
    try {
      const res = await fetch(`/api/cron/schedules/${scheduleId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: currentEnabled ? 0 : 1 }),
      });
      if (res.ok) {
        setItems((prev) =>
          prev.map((s) => (s.id === scheduleId ? { ...s, enabled: currentEnabled ? 0 : 1 } : s))
        );
        setMessage('Schedule toggled.');
        router.refresh();
      }
    } catch {
      setMessage('Error toggling schedule.');
    }
  }

  async function remove(scheduleId: string) {
    if (!confirm('Delete this schedule?')) return;
    setMessage('');
    try {
      const res = await fetch(`/api/cron/schedules/${scheduleId}`, { method: 'DELETE' });
      if (res.ok) {
        setItems((prev) => prev.filter((s) => s.id !== scheduleId));
        setMessage('Schedule deleted.');
        router.refresh();
      }
    } catch {
      setMessage('Error deleting schedule.');
    }
  }

  return (
    <div>
      {message && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-2 rounded mb-3 text-sm">
          {message}
        </div>
      )}
      <div className="border rounded-lg bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Task</th>
              <th className="px-4 py-2">Cron</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Last Run</th>
              <th className="px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">{s.name}</td>
                <td className="px-4 py-2">{s.task_name}</td>
                <td className="px-4 py-2 font-mono text-xs">{s.cron_expr}</td>
                <td className="px-4 py-2">
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${s.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'}`}
                  >
                    {s.enabled ? 'Active' : 'Paused'}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs text-gray-500">{s.last_run_at || 'Never'}</td>
                <td className="px-4 py-2 flex gap-2">
                  <button
                    onClick={() => toggle(s.id, s.enabled)}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    {s.enabled ? 'Pause' : 'Resume'}
                  </button>
                  <button
                    onClick={() => remove(s.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">No schedules found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
