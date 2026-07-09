// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import IndicatorForm from '../../indicator-form';
import { getIndicatorOps, getSourceTableColumns } from '../../../server-data';
import type { IndicatorInitial } from '../../indicator-form';

interface PageProps {
  params: Promise<{ name: string }>;
}

function safeParse(s: unknown): any {
  if (s == null || s === '') return null;
  if (typeof s !== 'string') return s;
  try {
    return JSON.parse(s);
  } catch {
    return s;
  }
}

export default async function EditIndicatorPage({ params }: PageProps) {
  const { name: rawName } = await params;
  const name = decodeURIComponent(rawName);

  const [{ ops, error: mcpError }, tableColumns] = await Promise.all([
    getIndicatorOps(),
    getSourceTableColumns(),
  ]);

  let indicator: any = null;
  try {
    const db = await getDb('daas');
    const rows = queryAll(db, 'SELECT * FROM indicator_rules WHERE name = ? LIMIT 1', [name]);
    indicator = rows[0] || null;
  } catch {
    // DB unavailable
  }

  if (!indicator) {
    return (
      <div>
        <Link href="/process/indicators" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
          ← Back to indicators
        </Link>
        <h1 className="text-2xl font-bold mb-2">Indicator not found</h1>
        <p className="text-gray-500 text-sm">
          No indicator named <code className="bg-gray-100 px-1 rounded">{name}</code> exists.
        </p>
      </div>
    );
  }

  const parsedParams = safeParse(indicator.params_json);
  const paramsText =
    parsedParams && typeof parsedParams === 'object'
      ? JSON.stringify(parsedParams, null, 2)
      : typeof indicator.params_json === 'string'
        ? indicator.params_json
        : '';

  const initial: IndicatorInitial = {
    name: indicator.name,
    datasource: indicator.datasource || '',
    function_name: indicator.function_name || '',
    source_table: indicator.source_table || '',
    date_column: indicator.date_column || '',
    value_column: indicator.value_column || '',
    op: indicator.op || '',
    params_json: paramsText,
    indicator_name: indicator.indicator_name || '',
    enabled: !!indicator.enabled,
  };

  return (
    <div>
      <Link
        href={`/process/indicators/${encodeURIComponent(name)}`}
        className="text-blue-600 hover:underline text-sm mb-4 inline-block"
      >
        ← Back to {name}
      </Link>
      <h1 className="text-2xl font-bold mb-6">Edit indicator</h1>
      <IndicatorForm
        mode="edit"
        initial={initial}
        ops={ops}
        tableColumns={tableColumns}
        mcpError={mcpError}
      />
    </div>
  );
}
