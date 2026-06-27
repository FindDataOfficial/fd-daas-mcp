'use client';

import { useState } from 'react';

interface Props {
  toolName: string;
  args: Record<string, unknown>;
  result?: unknown;
  error?: string;
  state: 'call' | 'result' | 'error';
}

export default function ToolCallCard({ toolName, args, result, error, state }: Props) {
  const [open, setOpen] = useState(false);

  const statusIcon = () => {
    switch (state) {
      case 'call':
        return (
          <svg className="w-4 h-4 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        );
      case 'error':
        return <span className="text-red-500 text-xs">✕</span>;
      case 'result':
        return <span className="text-green-500 text-xs">✓</span>;
    }
  };

  const resultStr = result
    ? typeof result === 'string'
      ? result
      : JSON.stringify(result, null, 2)
    : '';

  return (
    <div className="border rounded-lg bg-gray-50 my-2 text-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 transition-colors text-left"
      >
        {statusIcon()}
        <code className="text-xs font-mono text-gray-700">{toolName}</code>
        {state === 'call' && <span className="text-xs text-gray-400 ml-auto">running...</span>}
        {state === 'error' && <span className="text-xs text-red-500 ml-auto">failed</span>}
        {state === 'result' && (
          <span className="text-xs text-gray-400 ml-auto">
            {resultStr.length > 100 ? `${resultStr.slice(0, 100)}...` : resultStr.slice(0, 100)}
          </span>
        )}
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          {Object.keys(args).length > 0 && (
            <div>
              <div className="text-xs text-gray-500 mb-1">Arguments:</div>
              <pre className="text-xs bg-gray-100 p-2 rounded max-h-32 overflow-auto">
                {JSON.stringify(args, null, 2)}
              </pre>
            </div>
          )}
          {state === 'result' && resultStr && (
            <div>
              <div className="text-xs text-gray-500 mb-1">Result:</div>
              <pre className="text-xs bg-gray-100 p-2 rounded max-h-48 overflow-auto whitespace-pre-wrap">
                {resultStr}
              </pre>
            </div>
          )}
          {state === 'error' && error && (
            <div className="text-xs text-red-600 bg-red-50 p-2 rounded">{error}</div>
          )}
        </div>
      )}
    </div>
  );
}
