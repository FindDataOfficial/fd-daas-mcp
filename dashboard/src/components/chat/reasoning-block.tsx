'use client';

import { useState } from 'react';

interface Props {
  text: string;
}

export default function ReasoningBlock({ text }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="my-1">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700 transition-colors"
      >
        <svg
          className={`w-3 h-3 transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        {open ? 'Hide thinking' : 'Show thinking'}
      </button>
      {open && (
        <div className="mt-2 pl-4 border-l-2 border-gray-300 text-sm text-gray-500 whitespace-pre-wrap leading-relaxed">
          {text}
        </div>
      )}
    </div>
  );
}
