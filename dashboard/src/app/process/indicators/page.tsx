// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import EnabledToggle from '../enabled-toggle';
import IndicatorScoreInput from '@/components/indicators/indicator-score-input';

export default async function ProcessIndicatorsPage() {
  let indicators: any[] = [];

  try {
    const db = await getDb('daas');
    indicators = queryAll(
      db,
      `SELECT
         i.id, i.name, i.datasource, i.function_name, i.op, i.value_column,
         i.indicator_name, i.enabled, i.created_at,
         i.score,
         s.score AS datasource_default_score,
         COALESCE(i.score, s.score) AS effective_default_score,
         (SELECT o.value FROM observations o
            WHERE o.source = i.datasource
              AND o.function_name = i.function_name
              AND o.indicator = i.indicator_name
            ORDER BY o.date DESC LIMIT 1) AS latest_value,
         (SELECT o.date FROM observations o
            WHERE o.source = i.datasource
              AND o.function_name = i.function_name
              AND o.indicator = i.indicator_name
            ORDER BY o.date DESC LIMIT 1) AS latest_date
       FROM indicator_rules i
       LEFT JOIN sources s ON s.name = i.datasource
       ORDER BY i.created_at DESC`,
    );
  } catch {
    // DB / table not available
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Process Indicators</h1>
        <div className="flex items-center gap-3">
          <Link
            href="/process/indicators/collections"
            className="text-sm border border-gray-300 hover:bg-gray-50 px-3 py-1.5 rounded"
          >
            Collections
          </Link>
          <Link
            href="/process/indicators/new"
            className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded"
          >
            New indicator
          </Link>
        </div>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        Math indicator rules (<code>indicator_rules</code>) — each rule binds a source table + date/value
        column + op to an output indicator name, replayable via <code>run_indicator</code> (results upserted
        into <code>observations</code>). The <strong>score</strong> column sets a default priority/quality
        weight; a blank score inherits the datasource&rsquo;s default (<code>sources.score</code>).
      </p>

      <div className="border rounded-lg bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Datasource</th>
              <th className="px-4 py-2">Op</th>
              <th className="px-4 py-2">Value column</th>
              <th className="px-4 py-2">Indicator</th>
              <th className="px-4 py-2">Score</th>
              <th className="px-4 py-2">Enabled</th>
              <th className="px-4 py-2">Latest</th>
            </tr>
          </thead>
          <tbody>
            {indicators.map((i) => (
              <tr key={i.id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">
                  <Link
                    href={`/process/indicators/${encodeURIComponent(i.name)}`}
                    className="text-blue-600 hover:underline"
                  >
                    {i.name}
                  </Link>
                </td>
                <td className="px-4 py-2 font-mono text-xs">{i.datasource}</td>
                <td className="px-4 py-2 font-mono text-xs">{i.op}</td>
                <td className="px-4 py-2 font-mono text-xs">{i.value_column}</td>
                <td className="px-4 py-2 text-xs text-gray-600">{i.indicator_name}</td>
                <td className="px-4 py-2">
                  <IndicatorScoreInput
                    name={i.name}
                    initialScore={i.score == null ? null : Number(i.score)}
                    datasourceDefaultScore={i.datasource_default_score == null ? null : Number(i.datasource_default_score)}
                    effectiveDefaultScore={i.effective_default_score == null ? null : Number(i.effective_default_score)}
                  />
                </td>
                <td className="px-4 py-2">
                  <EnabledToggle kind="indicators" name={i.name} enabled={!!i.enabled} />
                </td>
                <td className="px-4 py-2 text-xs">
                  {i.latest_value != null ? (
                    <span>
                      <span className="font-mono">{i.latest_value}</span>
                      <span className="text-gray-400 ml-2">{i.latest_date}</span>
                    </span>
                  ) : (
                    <span className="text-gray-400 italic">No observations yet</span>
                  )}
                </td>
              </tr>
            ))}
            {indicators.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                  No indicators yet — click <span className="text-blue-600">New indicator</span> to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
