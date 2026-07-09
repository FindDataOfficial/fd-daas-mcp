// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import type { AgentOptions } from './server-data';

export interface AgentInitial {
  name: string;
  upstream: string;
  role: string;
  goal: string;
  backstory: string;
  model: string; // '' = default (shared LLM); otherwise a tier alias or model name
  enabled: boolean;
}

interface Props {
  mode: 'create' | 'edit';
  initial: AgentInitial;
  options: AgentOptions;
}

const TIER_ALIASES = ['high', 'balance', 'fast'];

export default function AgentForm({ mode, initial, options }: Props) {
  const router = useRouter();
  const [name, setName] = useState(initial.name);
  const [upstream, setUpstream] = useState(initial.upstream);
  const [role, setRole] = useState(initial.role);
  const [goal, setGoal] = useState(initial.goal);
  const [backstory, setBackstory] = useState(initial.backstory || '');
  const [model, setModel] = useState(initial.model || '');
  const [enabled, setEnabled] = useState(initial.enabled !== false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const upstreamNames = options.upstreams || [];
  const modelNames = (options.models || []).map((m) => m.name);
  // Tier aliases first, then concrete model names not already in the alias list.
  const modelOptions = [
    ...TIER_ALIASES,
    ...modelNames.filter((n) => !TIER_ALIASES.includes(n)),
  ];
  const mcpError = options.error;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    // '' → null (shared LLM fallback / clear override); else the chosen name.
    const modelArg = model === '' ? null : model;

    const payload: any = {
      name,
      upstream,
      role,
      goal,
      backstory: backstory || undefined,
      model: modelArg,
      enabled,
    };

    setSaving(true);
    try {
      const url =
        mode === 'create'
          ? '/api/agents'
          : `/api/agents/${encodeURIComponent(initial.name)}`;
      const body =
        mode === 'create'
          ? { action: 'create', ...payload }
          : { action: 'update', ...payload };
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({ error: 'Request failed' }));
      if (res.ok) {
        router.push(`/agents/${encodeURIComponent(payload.name)}`);
        router.refresh();
      } else {
        setError(data.error || `Failed (${res.status})`);
      }
    } catch (e: any) {
      setError(e?.message ?? 'Network error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-4">
      {mcpError && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2 rounded text-sm">
          leader-mcp unavailable ({mcpError}) — falling back to free-text inputs for upstream and model.
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-2 rounded text-sm">{error}</div>
      )}

      <div>
        <label className="block text-sm font-medium mb-1">Name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={mode === 'edit'}
          required
          className="w-full border rounded px-3 py-2 text-sm font-mono disabled:bg-gray-100"
        />
        {mode === 'edit' && (
          <p className="text-xs text-gray-400 mt-1">The agent name cannot be renamed.</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Upstream</label>
        {upstreamNames.length > 0 ? (
          <select
            value={upstream}
            onChange={(e) => setUpstream(e.target.value)}
            required
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          >
            <option value="">— pick a leader_upstreams name —</option>
            {upstreamNames.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={upstream}
            onChange={(e) => setUpstream(e.target.value)}
            required
            placeholder="e.g. edgartools"
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
        )}
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Role</label>
        <input
          type="text"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          required
          className="w-full border rounded px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Goal</label>
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          required
          rows={2}
          className="w-full border rounded px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Backstory (optional)</label>
        <textarea
          value={backstory}
          onChange={(e) => setBackstory(e.target.value)}
          rows={3}
          className="w-full border rounded px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Model</label>
        {modelOptions.length > 0 ? (
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          >
            <option value="">default (shared LLM)</option>
            {modelOptions.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="default (shared LLM)"
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
        )}
        <p className="text-xs text-gray-400 mt-1">
          A tier alias (high/balance/fast), a LEADER_MODELS entry name, or “default” for the shared LLM fallback.
        </p>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        enabled
      </label>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : mode === 'create' ? 'Create agent' : 'Save changes'}
        </button>
        <Link
          href={mode === 'edit' ? `/agents/${encodeURIComponent(initial.name)}` : '/agents'}
          className="px-4 py-2 rounded text-sm font-medium bg-gray-100 hover:bg-gray-200"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}
