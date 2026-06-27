'use client';

import { useState } from 'react';
import EChartsWrapper from '@/components/echarts-wrapper';
import type { EChartsOption } from 'echarts';

interface Props {
  json: string;
}

export default function EchartsBlock({ json }: Props) {
  const [showCode, setShowCode] = useState(false);
  const [error, setError] = useState<string | null>(null);

  let option: EChartsOption;
  try {
    option = JSON.parse(json);
  } catch {
    return (
      <div className="border border-red-200 bg-red-50 rounded-lg p-4 my-2">
        <p className="text-red-600 text-sm font-medium">Invalid chart configuration</p>
        <pre className="text-xs mt-2 text-red-500 max-h-32 overflow-auto">{json}</pre>
      </div>
    );
  }

  return (
    <div className="border rounded-lg bg-white my-2 overflow-hidden">
      <div className="flex justify-between items-center px-4 py-2 bg-gray-50 border-b">
        <span className="text-xs text-gray-500 font-medium">Chart</span>
        <button
          onClick={() => setShowCode(!showCode)}
          className="text-xs text-blue-600 hover:underline"
        >
          {showCode ? 'Hide Code' : 'Show Code'}
        </button>
      </div>
      {showCode && (
        <pre className="text-xs p-3 bg-gray-50 border-b max-h-48 overflow-auto">{json}</pre>
      )}
      <div className="p-2">
        {error ? (
          <div className="text-red-500 text-sm p-4">{error}</div>
        ) : (
          <EChartsWrapper
            option={option}
            style={{ height: 350 }}
          />
        )}
      </div>
    </div>
  );
}
