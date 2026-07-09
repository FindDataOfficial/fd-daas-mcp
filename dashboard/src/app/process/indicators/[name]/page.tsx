// @ts-nocheck
import { getDb, queryAll } from '@/lib/db';
import Link from 'next/link';
import EChartsWrapper from '@/components/echarts-wrapper';
import IndicatorControls from './indicator-controls';
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

const CHART_CAP = 365;

export default async function IndicatorDetailPage({ params }: PageProps) {
  const { name: rawName } = await params;
  const name = decodeURIComponent(rawName);

  let indicator: any = null;
  let observations: any[] = [];

  try {
    const db = await getDb('daas');
    const indRows = queryAll(db, 'SELECT * FROM indicator_rules WHERE name = ? LIMIT 1', [name]);
    indicator = indRows[0] || null;
    if (indicator) {
      observations = queryAll(
        db,
        `SELECT * FROM observations
         WHERE source = ? AND function_name = ? AND indicator = ?
         ORDER BY date ASC`,
        [indicator.datasource, indicator.function_name, indicator.indicator_name],
      );
    }
  } catch {
    // DB / table not available
  }

  if (!indicator) {
    return (
      <div>
        <Link href="/process/indicators" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
          ← Back to indicators
        </Link>
        <h1 className="text-2xl font-bold mb-2">Indicator not found</h1>
        <p className="text-gray-500 text-sm">
          No indicator named <code className="bg-gray-100 px-1 rounded">{name}</code> exists in{' '}
          <code>mcp/daas.db</code>.
        </p>
      </div>
    );
  }

  // Cap the chart to the latest CHART_CAP points (observations are ASC by date).
  const chartObs = observations.length > CHART_CAP ? observations.slice(-CHART_CAP) : observations;
  const chartDates = chartObs.map((o) => String(o.date));
  const chartValues = chartObs.map((o) => {
    const n = Number(o.value);
    return Number.isFinite(n) ? n : null;
  });

  const chartOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 48, right: 20, top: 20, bottom: 36 },
    xAxis: { type: 'category' as const, data: chartDates },
    yAxis: { type: 'value' as const },
    series: [
      {
        type: 'line' as const,
        data: chartValues,
        smooth: true,
        connectNulls: false,
        lineStyle: { width: 2 },
      },
    ],
  };

  // Recent observations table: most recent N first.
  const recent = [...observations].reverse().slice(0, 50);
  const parsedParams = safeParse(indicator.params_json);

  return (
    <div>
      <Link href="/process/indicators" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to indicators
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{indicator.name}</h1>
          <p className="text-xs text-gray-400 mt-1">
            created {indicator.created_at || '—'} · updated {indicator.updated_at || '—'}
          </p>
        </div>
        <IndicatorControls indicatorName={indicator.name} enabled={!!indicator.enabled} />
      </div>

      {/* Config */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Configuration</h2>
        <div className="border rounded-lg bg-white p-4 text-sm">
          <table className="w-full">
            <tbody>
              <tr className="border-t">
                <th className="px-3 py-2 text-left w-48 text-gray-500">datasource</th>
                <td className="px-3 py-2 font-mono text-xs">{indicator.datasource}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">function_name</th>
                <td className="px-3 py-2 font-mono text-xs">{indicator.function_name}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">source_table</th>
                <td className="px-3 py-2 font-mono text-xs">{indicator.source_table}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">date_column</th>
                <td className="px-3 py-2 font-mono text-xs">{indicator.date_column}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">value_column</th>
                <td className="px-3 py-2 font-mono text-xs">{indicator.value_column}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">op</th>
                <td className="px-3 py-2 font-mono text-xs">{indicator.op}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">indicator_name</th>
                <td className="px-3 py-2 text-xs">{indicator.indicator_name}</td>
              </tr>
              <tr className="border-t">
                <th className="px-3 py-2 text-left text-gray-500">enabled</th>
                <td className="px-3 py-2"><EnabledToggle kind="indicators" name={indicator.name} enabled={!!indicator.enabled} /></td>
              </tr>
              <tr className="border-t align-top">
                <th className="px-3 py-2 text-left text-gray-500">params_json</th>
                <td className="px-3 py-2"><JsonBlock value={parsedParams} /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Chart */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">
          Observation series
          <span className="ml-2 text-xs font-normal text-gray-500">
            showing {chartObs.length} of {observations.length} observations
          </span>
        </h2>
        {chartObs.length > 0 ? (
          <div className="border rounded-lg bg-white p-4">
            <EChartsWrapper option={chartOption} style={{ height: 360 }} />
          </div>
        ) : (
          <div className="border rounded-lg bg-white p-8 text-center text-gray-400">
            No observations yet — click <span className="text-blue-600">Run indicator</span> to compute.
          </div>
        )}
      </section>

      {/* Recent observations table */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Recent Observations ({recent.length})</h2>
        <div className="border rounded-lg bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="px-4 py-2">Date</th>
                <th className="px-4 py-2">Value</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((o, idx) => (
                <tr key={`${o.id ?? o.date}-${idx}`} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs">{o.date}</td>
                  <td className="px-4 py-2 font-mono text-xs">{o.value}</td>
                </tr>
              ))}
              {recent.length === 0 && (
                <tr>
                  <td colSpan={2} className="px-4 py-8 text-center text-gray-400">No observations</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
