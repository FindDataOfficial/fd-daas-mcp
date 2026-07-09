// @ts-nocheck
import Link from 'next/link';
import IndicatorForm from '../indicator-form';
import { getIndicatorOps, getSourceTableColumns } from '../../server-data';

export default async function NewIndicatorPage() {
  const [{ ops, error: mcpError }, tableColumns] = await Promise.all([
    getIndicatorOps(),
    getSourceTableColumns(),
  ]);

  const initial = {
    name: '',
    datasource: '',
    function_name: '',
    source_table: '',
    date_column: '',
    value_column: '',
    op: '',
    params_json: '',
    indicator_name: '',
    enabled: true,
  };

  return (
    <div>
      <Link href="/process/indicators" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to indicators
      </Link>
      <h1 className="text-2xl font-bold mb-6">New indicator</h1>
      <IndicatorForm
        mode="create"
        initial={initial}
        ops={ops}
        tableColumns={tableColumns}
        mcpError={mcpError}
      />
    </div>
  );
}
