// @ts-nocheck
'use client';

import { useState } from 'react';

interface Props {
  /** The raw payload (already parsed from JSON, or a string). */
  value: unknown;
  /** Approximate byte budget for the collapsed view. */
  budget?: number;
}

const DEFAULT_BUDGET = 5000;

function toText(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/** Truncated pretty-JSON block with a "Show full" toggle. Shared by the rules
 *  and indicators detail pages (mirrors the workflows output-block pattern). */
export default function JsonBlock({ value, budget = DEFAULT_BUDGET }: Props) {
  const [expanded, setExpanded] = useState(false);
  const text = toText(value);

  if (!text) {
    return <pre className="text-xs text-gray-400 italic">(empty)</pre>;
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
