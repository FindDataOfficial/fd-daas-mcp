// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import RuleControls from './rule-controls';
import EnabledToggle from '../../enabled-toggle';
import JsonBlock from '@/components/json-block';

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

export default async function RuleDetailPage({ params }: PageProps) {
  const { name: rawName } = await params;
  const name = decodeURIComponent(rawName);

  let rule: any = null;
  let results: any[] = [];

  try {
    const db = await getDb('daas');
    const ruleRows = queryAll(db, 'SELECT * FROM process_rules WHERE name = ? LIMIT 1', [name]);
    rule = ruleRows[0] || null;
    if (rule) {
      results = queryAll(
        db,
        'SELECT * FROM process_results WHERE rule_id = ? ORDER BY run_at DESC, id DESC LIMIT 50',
        [rule.id],
      );
    }
  } catch {
    // DB / table not available
  }

  if (!rule) {
    return (
      <div>
        <Link href="/process/rules" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
          ← Back to rules
        </Link>
        <h1 className="text-2xl font-bold mb-2">Rule not found</h1>
        <p className="text-gray-500 text-sm">
          No rule named <code className="bg-gray-100 px-1 rounded">{name}</code> exists in{' '}
          <code>mcp/daas.db</code>.
        </p>
      </div>
    );
  }

  const schema = safeParse(rule.schema_json);

  return (
    <div>
      <Link href="/process/rules" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to rules
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{rule.name}</h1>
          <p className="text-xs text-gray-400 mt-1">
            created {rule.created_at || '—'} · updated {rule.updated_at || '—'}
          </p>
        </div>
        <RuleControls ruleName={rule.name} enabled={!!rule.enabled} />
      </div>

      {/* Config */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Configuration</h2>
        <div className="border rounded-lg bg-white p-4 text-sm">
          <table className="w-full">
            <tbody>
              <tr className="border-t">
                <th className="px-3 py-2 text-left w-48 text-gray-500">source_table</th>
                <td className="px-3 py-2 font-mono text-xs">{rule.source_table}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">text_column</th>
                <td className="px-3 py-2 font-mono text-xs">{rule.text_column}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">model</th>
                <td className="px-3 py-2 text-xs">{rule.model || <span className="italic text-gray-400">default</span>}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">max_chars</th>
                <td className="px-3 py-2 text-xs">{rule.max_chars ?? 12000}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">datasource</th>
                <td className="px-3 py-2 font-mono text-xs">{rule.datasource || '—'}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">enabled</th>
                <td className="px-3 py-2"><EnabledToggle kind="rules" name={rule.name} enabled={!!rule.enabled} /></td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">last_rowid (cursor)</th>
                <td className="px-3 py-2 text-xs">{rule.last_rowid ?? 0}</td>
              </tr>
              {rule.prompt && (
                <tr className="border-t align-top">
                  <th className="px-3 py-2 text-left text-gray-500">prompt</th>
                  <td className="px-3 py-2"><pre className="text-xs bg-gray-50 border rounded p-2 whitespace-pre-wrap">{rule.prompt}</pre></td>
                </tr>
              )}
              <tr className="border-t align-top">
                <th className="px-3 py-2 text-left text-gray-500">schema_json</th>
                <td className="px-3 py-2"><JsonBlock value={schema} /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Recent results */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Recent Results ({results.length})</h2>
        <div className="space-y-3">
          {results.map((r) => (
            <div key={r.id} className="border rounded-lg bg-white p-4">
              <div className="flex items-center gap-3 mb-2">
                <span className="font-medium text-sm">row #{r.source_rowid}</span>
                <span className="text-xs text-gray-500">{r.model || '—'}</span>
                <span className="text-xs text-gray-400">ran {r.run_at || '—'}</span>
              </div>
              <JsonBlock value={safeParse(r.extracted_json)} />
            </div>
          ))}
          {results.length === 0 && (
            <div className="border rounded-lg bg-white p-8 text-center text-gray-400">
              No results yet — click <span className="text-blue-600">Run rule</span> to extract.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
