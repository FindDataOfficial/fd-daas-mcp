// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import RuleForm from '../../rule-form';
import { getModels, getSourceTableColumns } from '../../../server-data';
import type { RuleInitial } from '../../rule-form';

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

export default async function EditRulePage({ params }: PageProps) {
  const { name: rawName } = await params;
  const name = decodeURIComponent(rawName);

  const [{ models, error: mcpError }, tableColumns] = await Promise.all([
    getModels(),
    getSourceTableColumns(),
  ]);

  let rule: any = null;
  try {
    const db = await getDb('daas');
    const rows = queryAll(db, 'SELECT * FROM process_rules WHERE name = ? LIMIT 1', [name]);
    rule = rows[0] || null;
  } catch {
    // DB unavailable
  }

  if (!rule) {
    return (
      <div>
        <Link href="/process/rules" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
          ← Back to rules
        </Link>
        <h1 className="text-2xl font-bold mb-2">Rule not found</h1>
        <p className="text-gray-500 text-sm">
          No rule named <code className="bg-gray-100 px-1 rounded">{name}</code> exists.
        </p>
      </div>
    );
  }

  const parsedSchema = safeParse(rule.schema_json);
  const schemaText =
    parsedSchema && typeof parsedSchema === 'object'
      ? JSON.stringify(parsedSchema, null, 2)
      : typeof rule.schema_json === 'string'
        ? rule.schema_json
        : '{}';

  const initial: RuleInitial = {
    name: rule.name,
    source_table: rule.source_table || '',
    text_column: rule.text_column || '',
    schema_json: schemaText,
    prompt: rule.prompt || '',
    model: rule.model || '',
    max_chars: rule.max_chars ?? 12000,
    datasource: rule.datasource || '',
    enabled: !!rule.enabled,
  };

  return (
    <div>
      <Link
        href={`/process/rules/${encodeURIComponent(name)}`}
        className="text-blue-600 hover:underline text-sm mb-4 inline-block"
      >
        ← Back to {name}
      </Link>
      <h1 className="text-2xl font-bold mb-6">Edit rule</h1>
      <RuleForm
        mode="edit"
        initial={initial}
        models={models}
        tableColumns={tableColumns}
        mcpError={mcpError}
      />
    </div>
  );
}
