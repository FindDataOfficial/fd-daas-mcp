'use client';

import { useEffect, useRef, useState } from 'react';
import { useChat } from '@ai-sdk/react';
import { TextStreamChatTransport } from 'ai';
import MessageList from '@/components/chat/message-list';
import ChatInput from '@/components/chat/chat-input';

interface Props {
  collectionName: string;
  itemCount: number;
}

const HISTORY_KEY_PREFIX = 'collection-chat:';

function loadHistory(name: string): any[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(HISTORY_KEY_PREFIX + name);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveHistory(name: string, messages: any[]) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(HISTORY_KEY_PREFIX + name, JSON.stringify(messages));
  } catch { /* quota — ignore */ }
}

export default function ChatPane({ collectionName, itemCount }: Props) {
  const transport = useRef<TextStreamChatTransport<any> | null>(null);
  if (!transport.current || (transport.current as any).api !== `/api/collections/${encodeURIComponent(collectionName)}/chat`) {
    transport.current = new TextStreamChatTransport<any>({
      api: `/api/collections/${encodeURIComponent(collectionName)}/chat`,
    });
  }

  const [error, setError] = useState<string | null>(null);

  const chat = useChat({
    id: `collection:${collectionName}`,
    transport: transport.current,
    onError: (err: any) => setError(err?.message ?? String(err)),
  } as any);

  const messages = (chat as any).messages ?? [];
  const setMessages = (chat as any).setMessages as ((m: any[]) => void) | undefined;
  const sendMessage = (chat as any).sendMessage as ((p: { text: string }) => void) | undefined;
  const status = (chat as any).status;
  const loading = status === 'submitted' || status === 'streaming';

  // Rehydrate per-collection history when the collection changes.
  useEffect(() => {
    const history = loadHistory(collectionName);
    if (setMessages) setMessages(history);
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionName]);

  // Persist on every update — small dataset, fine for local use.
  useEffect(() => {
    if (messages.length > 0) saveHistory(collectionName, messages);
  }, [messages, collectionName]);

  const handleSend = (text: string) => {
    setError(null);
    if (sendMessage) sendMessage({ text });
  };

  const handleReset = () => {
    if (setMessages) setMessages([]);
    saveHistory(collectionName, []);
    setError(null);
  };

  return (
    <div className="h-full flex flex-col bg-white border-l">
      <div className="border-b px-4 py-2 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold">Chat</div>
          <div className="text-xs text-gray-500">
            {itemCount > 0
              ? `Scoped to ${itemCount} item${itemCount === 1 ? '' : 's'} in "${collectionName}"`
              : `Collection is empty — add datasources first`}
          </div>
        </div>
        <button
          onClick={handleReset}
          className="text-xs text-blue-600 hover:underline"
        >
          Clear
        </button>
      </div>
      {error && (
        <div className="bg-red-50 border-b border-red-200 px-3 py-2 text-xs text-red-700 flex items-start gap-2">
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">×</button>
        </div>
      )}
      <MessageList messages={messages} loading={loading} />
      <ChatInput onSend={handleSend} disabled={loading} />
    </div>
  );
}
