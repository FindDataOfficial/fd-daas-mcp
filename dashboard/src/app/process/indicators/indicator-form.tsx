// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export interface IndicatorInitial {
  name: string;
  datasource: string;
  function_name: string;
  source_table: string;
  date_column: string;
  value_column: string;
  op: string;
  params_json: string; // raw JSON text
  indicator_name: string;
  enabled: boolean;
}

interface Props {
  mode: 'create' | 'edit';
  initial: IndicatorInitial;
  ops: { name: string; description?: string }[];
  tableColumns: Record<string, string[]>;
  mcpError?: string;
}

export default function IndicatorForm({ mode, initial, ops, tableColumns, mcpError }: Props) {
  const router = useRouter();
  const [name, setName] = useState(initial.name);
  const [datasource, setDatasource] = useState(initial.datasource);
  const [functionName, setFunctionName] = useState(initial.function_name);
  const [sourceTable, setSourceTable] = useState(initial.source_table);
  const [dateColumn, setDateColumn] = useState(initial.date_column);
  const [valueColumn, setValueColumn] = useState(initial.value_column);
  const [op, setOp] = useState(initial.op);
  const [paramsText, setParamsText] = useState(initial.params_json);
  const [paramsErr, setParamsErr] = useState('');
  const [indicatorName, setIndicatorName] = useState(initial.indicator_name);
  const [enabled, setEnabled] = useState(initial.enabled);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const tableNames = Object.keys(tableColumns).sort();
  const columnsForTable = sourceTable ? tableColumns[sourceTable] || [] : [];

  function validateParams(text: string): { ok: boolean; value?: any } {
    if (!text.trim()) return { ok: true, value: undefined };
    try {
      return { ok: true, value: JSON.parse(text) };
    } catch {
      return { ok: false };
    }
  }

  function onParamsChange(text: string) {
    setParamsText(text);
    setParamsErr(validateParams(text).ok ? '' : 'Invalid JSON');
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    const v = validateParams(paramsText);
    if (!v.ok) {
      setParamsErr('Invalid JSON — fix before saving');
      return;
    }

    const payload: any = {
      name,
      datasource,
      source_table: sourceTable,
      date_column: dateColumn,
      value_column: valueColumn,
      op,
      params: v.value,
      function_name: functionName || undefined,
      indicator_name: indicatorName || undefined,
      enabled,
    };

    setSaving(true);
    try {
      const url =
        mode === 'create'
          ? '/api/process/indicators'
          : `/api/process/indicators/${encodeURIComponent(initial.name)}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mode === 'create' ? { action: 'create', ...payload } : { action: 'update', ...payload }),
      });
      const data = await res.json().catch(() => ({ error: 'Request failed' }));
      if (res.ok) {
        router.push(`/process/indicators/${encodeURIComponent(payload.name)}`);
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

  const colSelect = (value: string, onChange: (v: string) => void, placeholder: string) => (
    columnsForTable.length > 0 ? (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
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
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required
        placeholder={placeholder}
        className="w-full border rounded px-3 py-2 text-sm font-mono"
      />
    )
  );

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
        {mode === 'edit' && <p className="text-xs text-gray-400 mt-1">The indicator name cannot be renamed.</p>}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Datasource</label>
          <input
            type="text"
            value={datasource}
            onChange={(e) => setDatasource(e.target.value)}
            required
            placeholder="daas sources.name"
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">function_name (optional)</label>
          <input
            type="text"
            value={functionName}
            onChange={(e) => setFunctionName(e.target.value)}
            placeholder="defaults to source_table"
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Source table</label>
        {tableNames.length > 0 ? (
          <select
            value={sourceTable}
            onChange={(e) => {
              setSourceTable(e.target.value);
              setDateColumn('');
              setValueColumn('');
            }}
            required
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          >
            <option value="">— pick a table —</option>
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
            placeholder="any table in daas.db"
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Date column</label>
          {colSelect(dateColumn, setDateColumn, 'date')}
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Value column</label>
          {colSelect(valueColumn, setValueColumn, 'value')}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Op</label>
          {ops.length > 0 ? (
            <select
              value={op}
              onChange={(e) => setOp(e.target.value)}
              required
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            >
              <option value="">— pick an op —</option>
              {ops.map((o: any) => (
                <option key={o.name} value={o.name} title={o.description}>
                  {o.name}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={op}
              onChange={(e) => setOp(e.target.value)}
              required
              placeholder="sma / ema / rsi / pct_change / …"
              className="w-full border rounded px-3 py-2 text-sm font-mono"
            />
          )}
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">indicator_name (optional)</label>
          <input
            type="text"
            value={indicatorName}
            onChange={(e) => setIndicatorName(e.target.value)}
            placeholder="defaults to rule name"
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Params (JSON, optional)</label>
        <textarea
          value={paramsText}
          onChange={(e) => onParamsChange(e.target.value)}
          rows={4}
          className={`w-full border rounded px-3 py-2 text-sm font-mono ${paramsErr ? 'border-red-400' : ''}`}
          placeholder='{"window": 5}'
        />
        {paramsErr && <p className="text-xs text-red-600 mt-1">{paramsErr}</p>}
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        enabled
      </label>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving || !!paramsErr}
          className="px-4 py-2 rounded text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : mode === 'create' ? 'Create indicator' : 'Save changes'}
        </button>
        <Link
          href={mode === 'edit' ? `/process/indicators/${encodeURIComponent(initial.name)}` : '/process/indicators'}
          className="px-4 py-2 rounded text-sm font-medium bg-gray-100 hover:bg-gray-200"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}
