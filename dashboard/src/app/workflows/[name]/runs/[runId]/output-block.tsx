// @ts-nocheck
'use client';

import { useState } from 'react';

interface Props {
  /** The raw output payload (already parsed from `output_json`, or a string). */
  output: unknown;
  /** Approximate byte budget for the collapsed view. */
  budget?: number;
}

const DEFAULT_BUDGET = 5000;

function toText(output: unknown): string {
  if (output == null) return '';
  if (typeof output === 'string') return output;
  try {
    return JSON.stringify(output, null, 2);
  } catch {
    return String(output);
  }
}

export default function OutputBlock({ output, budget = DEFAULT_BUDGET }: Props) {
  const [expanded, setExpanded] = useState(false);
  const text = toText(output);

  if (!text) {
    return <pre className="text-xs text-gray-400 italic">(no output)</pre>;
  }

  const isLong = text.length > budget;
  const shown = expanded || !isLong ? text : text.slice(0, budget);

  return (
    <div>
      <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-96 whitespace-pre-wrap break-all">
        {shown}
        {!expanded && isLong ? '\n… (truncated)' : ''}
      </pre>
      {isLong && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-blue-600 hover:underline mt-1"
        >
          {expanded ? 'Show truncated' : `Show full (${text.length.toLocaleString()} chars)`}
        </button>
      )}
    </div>
  );
}
