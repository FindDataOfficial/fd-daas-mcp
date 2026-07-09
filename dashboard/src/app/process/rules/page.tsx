// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import EnabledToggle from '../enabled-toggle';

export default async function ProcessRulesPage() {
  let rules: any[] = [];

  try {
    const db = await getDb('daas');
    rules = queryAll(
      db,
      `SELECT
         r.id, r.name, r.source_table, r.text_column, r.model,
         r.enabled, r.last_rowid, r.created_at,
         (SELECT COUNT(*) FROM process_results p WHERE p.rule_id = r.id) AS result_count
       FROM process_rules r
       ORDER BY r.created_at DESC`,
    );
  } catch {
    // DB / table not available — render empty state
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Process Rules</h1>
        <Link
          href="/process/rules/new"
          className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded"
        >
          New rule
        </Link>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        LLM extraction rules (<code>process_rules</code>) — each rule binds a scraped source table + text
        column to a JSON schema and model, replayable via <code>run_rule</code>.
      </p>

      <div className="border rounded-lg bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Source table</th>
              <th className="px-4 py-2">Text column</th>
              <th className="px-4 py-2">Model</th>
              <th className="px-4 py-2">Enabled</th>
              <th className="px-4 py-2">Cursor (last_rowid)</th>
              <th className="px-4 py-2">Results</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">
                  <Link
                    href={`/process/rules/${encodeURIComponent(r.name)}`}
                    className="text-blue-600 hover:underline"
                  >
                    {r.name}
                  </Link>
                </td>
                <td className="px-4 py-2 font-mono text-xs">{r.source_table}</td>
                <td className="px-4 py-2 font-mono text-xs">{r.text_column}</td>
                <td className="px-4 py-2 text-xs text-gray-600">
                  {r.model || <span className="italic text-gray-400">default</span>}
                </td>
                <td className="px-4 py-2">
                  <EnabledToggle kind="rules" name={r.name} enabled={!!r.enabled} />
                </td>
                <td className="px-4 py-2 text-xs text-gray-500">{r.last_rowid ?? 0}</td>
                <td className="px-4 py-2 text-xs">{r.result_count ?? 0}</td>
              </tr>
            ))}
            {rules.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  No rules yet — click <span className="text-blue-600">New rule</span> to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
