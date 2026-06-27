'use client';

import { useEffect, useRef } from 'react';
import MessageBubble from './message-bubble';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  parts: Array<{
    type: string;
    text?: string;
    toolName?: string;
    toolCallId?: string;
    args?: Record<string, unknown>;
    result?: unknown;
    errorText?: string;
    state?: string;
  }>;
}

interface Props {
  messages: Message[];
  loading?: boolean;
}

export default function MessageList({ messages, loading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0 && !loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <div className="text-center">
          <p className="text-lg mb-2">Start a conversation</p>
          <p className="text-sm">Ask questions, query data, or request visualizations</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} role={msg.role} parts={msg.parts} />
      ))}
      {loading && (
        <div className="flex justify-start mb-4">
          <div className="bg-white border rounded-lg px-4 py-3">
            <div className="flex gap-1">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
