// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface Props {
  workflowName: string;
  /** When omitted, renders the full-run button; when set, renders a single-step button. */
  stepSortOrder?: number;
}

export default function RunControls({ workflowName, stepSortOrder }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const isStep = typeof stepSortOrder === 'number';
  const label = isStep ? 'Run this step' : 'Run all steps';

  async function handleRun() {
    setBusy(true);
    setError('');
    try {
      const body = isStep
        ? { mode: 'step', step_sort_order: stepSortOrder }
        : { mode: 'all' };
      const res = await fetch(
        `/api/workflows/${encodeURIComponent(workflowName)}/runs`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
      );
      if (res.ok) {
        router.refresh();
      } else {
        const data = await res.json().catch(() => ({ error: 'Request failed' }));
        setError(data.error || `Failed (${res.status})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Network error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col">
      <button
        onClick={handleRun}
        disabled={busy}
        className={`px-3 py-1.5 rounded text-xs font-medium text-white disabled:opacity-50 ${
          isStep ? 'bg-gray-600 hover:bg-gray-700' : 'bg-blue-600 hover:bg-blue-700'
        }`}
      >
        {busy ? 'Running…' : label}
      </button>
      {error && <span className="text-xs text-red-600 mt-1 max-w-[16rem]">{error}</span>}
    </span>
  );
}
