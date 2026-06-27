'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface Props {
  task: {
    id: string;
    name: string;
    command: string;
    description: string;
    timeout: number;
  };
}

export default function TaskForm({ task }: Props) {
  const router = useRouter();
  const [command, setCommand] = useState(task.command || '');
  const [description, setDescription] = useState(task.description || '');
  const [timeout, setTimeout_] = useState(String(task.timeout || 60));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function handleSave() {
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const res = await fetch(`/api/cron/tasks/${task.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, description, timeout: Number(timeout) }),
      });
      if (res.ok) {
        setMessage('Task updated.');
        router.refresh();
      } else {
        const data = await res.json();
        setError(data.error || 'Failed to update');
      }
    } catch {
      setError('Network error');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete task "${task.name}" and all its schedules?`)) return;
    setSaving(true);
    try {
      const res = await fetch(`/api/cron/tasks/${task.id}`, { method: 'DELETE' });
      if (res.ok) {
        router.push('/cron/tasks/deleted?done=deleted');
      } else {
        const data = await res.json();
        setError(data.error || 'Failed to delete');
      }
    } catch {
      setError('Network error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-lg">
      {message && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded mb-4">
          {message}
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="bg-white border rounded-lg p-6">
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            type="text"
            value={task.name}
            disabled
            className="w-full px-3 py-2 border rounded bg-gray-50 text-gray-500 text-sm"
          />
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Command</label>
          <textarea
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border rounded text-sm font-mono"
          />
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-1">Timeout (seconds)</label>
          <input
            type="number"
            value={timeout}
            onChange={(e) => setTimeout_(e.target.value)}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            onClick={handleDelete}
            disabled={saving}
            className="px-4 py-2 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
          >
            Delete Task
          </button>
        </div>
      </div>
    </div>
  );
}
