// @ts-nocheck
import Link from 'next/link';
import RuleForm from '../rule-form';
import { getModels, getSourceTableColumns } from '../../server-data';

export default async function NewRulePage() {
  const [{ models, error: mcpError }, tableColumns] = await Promise.all([
    getModels(),
    getSourceTableColumns(),
  ]);

  const initial = {
    name: '',
    source_table: '',
    text_column: '',
    schema_json: '{\n  "type": "object",\n  "properties": {}\n}',
    prompt: '',
    model: '',
    max_chars: 12000,
    datasource: '',
    enabled: true,
  };

  return (
    <div>
      <Link href="/process/rules" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to rules
      </Link>
      <h1 className="text-2xl font-bold mb-6">New rule</h1>
      <RuleForm
        mode="create"
        initial={initial}
        models={models}
        tableColumns={tableColumns}
        mcpError={mcpError}
      />
    </div>
  );
}
