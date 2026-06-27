'use client';

import EChartsWrapper from '@/components/echarts-wrapper';
import type { ExecutionRow, ScheduleRow } from '@/lib/schema';
import type { EChartsOption } from 'echarts';

interface Props {
  executions: ExecutionRow[];
  schedules: ScheduleRow[];
}

export default function CronCharts({ executions, schedules }: Props) {
  // Execution history: group by date
  const byDate = new Map<string, { completed: number; failed: number }>();
  for (const e of executions) {
    const date = e.started_at?.slice(0, 10) || 'unknown';
    if (!byDate.has(date)) byDate.set(date, { completed: 0, failed: 0 });
    const entry = byDate.get(date)!;
    if (e.status === 'completed') entry.completed++;
    else if (e.status === 'failed') entry.failed++;
  }
  const dates = [...byDate.keys()].sort();

  const execOption: EChartsOption = {
    title: { text: 'Execution History', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['Completed', 'Failed'], bottom: 0 },
    xAxis: { data: dates, axisLabel: { rotate: 45 } },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'Completed',
        type: 'bar',
        stack: 'total',
        data: dates.map((d) => byDate.get(d)!.completed),
        color: '#22c55e',
      },
      {
        name: 'Failed',
        type: 'bar',
        stack: 'total',
        data: dates.map((d) => byDate.get(d)!.failed),
        color: '#ef4444',
      },
    ],
  };

  // Schedule status pie
  const activeCount = schedules.filter((s) => s.enabled).length;
  const pausedCount = schedules.length - activeCount;
  const scheduleOption: EChartsOption = {
    title: { text: 'Schedule Status', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        data: [
          { name: 'Active', value: activeCount, itemStyle: { color: '#22c55e' } },
          { name: 'Paused', value: pausedCount, itemStyle: { color: '#9ca3af' } },
        ],
      },
    ],
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-white border rounded-lg p-4">
        <EChartsWrapper option={execOption} />
      </div>
      <div className="bg-white border rounded-lg p-4">
        <EChartsWrapper option={scheduleOption} />
      </div>
    </div>
  );
}
