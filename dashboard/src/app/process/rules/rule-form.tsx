// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export interface RuleInitial {
  name: string;
  source_table: string;
  text_column: string;
  schema_json: string; // raw JSON text
  prompt: string;
  model: string;
  max_chars: number;
  datasource: string;
  enabled: boolean;
}

interface Props {
  mode: 'create' | 'edit';
  initial: RuleInitial;
  models: string[];
  tableColumns: Record<string, string[]>;
  mcpError?: string;
}

export default function RuleForm({ mode, initial, models, tableColumns, mcpError }: Props) {
  const router = useRouter();
  const [name, setName] = useState(initial.name);
  const [sourceTable, setSourceTable] = useState(initial.source_table);
  const [textColumn, setTextColumn] = useState(initial.text_column);
  const [schemaText, setSchemaText] = useState(initial.schema_json);
  const [schemaErr, setSchemaErr] = useState('');
  const [prompt, setPrompt] = useState(initial.prompt);
  const [model, setModel] = useState(initial.model);
  const [maxChars, setMaxChars] = useState(String(initial.max_chars ?? 12000));
  const [datasource, setDatasource] = useState(initial.datasource);
  const [enabled, setEnabled] = useState(initial.enabled);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const tableNames = Object.keys(tableColumns).sort();
  const columnsForTable = sourceTable ? tableColumns[sourceTable] || [] : [];

  function validateSchema(text: string): { ok: boolean; value?: any } {
    if (!text.trim()) return { ok: false };
    try {
      return { ok: true, value: JSON.parse(text) };
    } catch (e: any) {
      return { ok: false };
    }
  }

  function onSchemaChange(text: string) {
    setSchemaText(text);
    const v = validateSchema(text);
    setSchemaErr(v.ok ? '' : 'Invalid JSON');
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    const v = validateSchema(schemaText);
    if (!v.ok) {
      setSchemaErr('Invalid JSON — fix before saving');
      return;
    }

    const payload: any = {
      name,
      source_table: sourceTable,
      text_column: textColumn,
      schema: v.value,
      prompt: prompt || undefined,
      model: model || undefined,
      max_chars: Number(maxChars) || 12000,
      datasource: datasource || undefined,
      enabled,
    };

    setSaving(true);
    try {
      const url =
        mode === 'create'
          ? '/api/process/rules'
          : `/api/process/rules/${encodeURIComponent(initial.name)}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mode === 'create' ? { action: 'create', ...payload } : { action: 'update', ...payload }),
      });
      const data = await res.json().catch(() => ({ error: 'Request failed' }));
      if (res.ok) {
        router.push(`/process/rules/${encodeURIComponent(payload.name)}`);
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
          daas-mcp unavailable ({mcpError}) — falling back to free-text inputs.
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
          <p className="text-xs text-gray-400 mt-1">The rule name cannot be renamed.</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Source table</label>
          {tableNames.length > 0 ? (
            <select
              value={sourceTable}
              onChange={(e) => {
                setSourceTable(e.target.value);
                setTextColumn('');
              }}
              required
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            >
              <option value="">— pick a scraw_* table —</option>
              {tableNames.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={sourceTable}
              onChange={(e) => setSourceTable(e.target.value)}
              required
              placeholder="scraw_<slug>"
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            />
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Text column</label>
          {columnsForTable.length > 0 ? (
            <select
              value={textColumn}
              onChange={(e) => setTextColumn(e.target.value)}
              required
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            >
              <option value="">— pick a column —</option>
              {columnsForTable.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={textColumn}
              onChange={(e) => setTextColumn(e.target.value)}
              required
              placeholder="text"
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            />
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Model</label>
          {models.length > 0 ? (
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            >
              <option value="">default</option>
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="default"
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            />
          )}
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">max_chars</label>
          <input
            type="number"
            value={maxChars}
            onChange={(e) => setMaxChars(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Datasource (optional)</label>
        <input
          type="text"
          value={datasource}
          onChange={(e) => setDatasource(e.target.value)}
          placeholder="daas sources.name (traceability only)"
          className="w-full border rounded px-3 py-2 text-sm font-mono"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Prompt (optional)</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          className="w-full border rounded px-3 py-2 text-sm font-mono"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Schema (JSON)</label>
        <textarea
          value={schemaText}
          onChange={(e) => onSchemaChange(e.target.value)}
          rows={10}
          required
          className={`w-full border rounded px-3 py-2 text-sm font-mono ${schemaErr ? 'border-red-400' : ''}`}
          placeholder='{"type":"object","properties":{...}}'
        />
        {schemaErr && <p className="text-xs text-red-600 mt-1">{schemaErr}</p>}
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        enabled
      </label>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving || !!schemaErr}
          className="px-4 py-2 rounded text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : mode === 'create' ? 'Create rule' : 'Save changes'}
        </button>
        <Link
          href={mode === 'edit' ? `/process/rules/${encodeURIComponent(initial.name)}` : '/process/rules'}
          className="px-4 py-2 rounded text-sm font-medium bg-gray-100 hover:bg-gray-200"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}
