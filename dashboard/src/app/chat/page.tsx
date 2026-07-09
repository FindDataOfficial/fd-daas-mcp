'use client';

import { useState, useCallback, useMemo } from 'react';
import { useChat } from '@ai-sdk/react';
import ChatInput from '@/components/chat/chat-input';
import MessageList from '@/components/chat/message-list';
import {
  loadConversations,
  saveConversation,
  deleteConversation,
  getConversation,
  generateId,
  type ChatConversation,
} from '@/lib/chat-store';

// MCP servers selectable in the chat. composite-mcp is the default (curated
// multi-upstream surface that ships the render_stock_summary demo UI tool).
const SERVERS = [
  'composite-mcp',
  'leader-mcp',
  'daas-mcp',
  'cron-mcp',
  'dashboard-mcp',
  'alerts-mcp',
];

const DEFAULT_SERVER = process.env.NEXT_PUBLIC_MCP_SERVER || 'composite-mcp';

export default function ChatPage() {
  const [conversationId, setConversationId] = useState<string>(() => generateId());
  const [conversations, setConversations] = useState<ChatConversation[]>(() => loadConversations());
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [server, setServer] = useState<string>(() => {
    if (typeof window === 'undefined') return DEFAULT_SERVER;
    return window.localStorage.getItem('chat-mcp-server') || DEFAULT_SERVER;
  });

  const initialMessages = useMemo(
    // Stored conversations are UIMessage-shaped; useChat's initialMessages
    // types as Message[] (legacy) but accepts UIMessage[] at runtime.
    () => (getConversation(conversationId) as any) ?? [],
    [conversationId],
  );

  const {
    messages,
    append,
    status,
    error: chatError,
    setMessages,
  } = useChat({
    api: '/api/chat',
    id: conversationId,
    initialMessages,
    // ponytail: inject the selected MCP server into every request body so
    // /api/chat dispatches to the right client (raw for composite-mcp,
    // @ai-sdk/mcp otherwise). Called per request, so it captures the current
    // `server` value.
    experimental_prepareRequestBody: ({ messages: msgs }) => ({
      messages: msgs,
      server,
    }),
    maxSteps: 10,
    onError: (err) => setError(err.message),
  });

  const loading = status === 'submitted' || status === 'streaming';

  const handleSend = useCallback(
    (text: string) => {
      setError(null);
      void append({ role: 'user', content: text });
    },
    [append],
  );

  // Persist messages on change
  if (messages.length > 0) {
    saveConversation(conversationId, messages as any);
  }

  const handleServerChange = (next: string) => {
    setServer(next);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('chat-mcp-server', next);
    }
  };

  const handleNewChat = () => {
    const newId = generateId();
    setConversationId(newId);
    setMessages([]);
    setError(null);
    setConversations(loadConversations());
  };

  const handleLoadConversation = (id: string) => {
    setConversationId(id);
    setError(null);
    setSidebarOpen(false);
  };

  const handleDeleteConversation = (id: string) => {
    deleteConversation(id);
    if (id === conversationId) {
      const newId = generateId();
      setConversationId(newId);
      setMessages([]);
    }
    setConversations(loadConversations());
  };

  return (
    <div className="flex h-full">
      {/* Conversation sidebar */}
      {sidebarOpen && (
        <div className="w-64 border-r bg-gray-50 flex flex-col shrink-0">
          <div className="p-3 border-b flex justify-between items-center">
            <span className="text-sm font-semibold">Conversations</span>
            <button
              onClick={() => setSidebarOpen(false)}
              className="text-gray-400 hover:text-gray-600 text-xs"
            >
              ✕
            </button>
          </div>
          <div className="p-2">
            <button
              onClick={handleNewChat}
              className="w-full text-left px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              + New Chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`flex items-center justify-between px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 ${
                  conv.id === conversationId ? 'bg-blue-100' : ''
                }`}
                onClick={() => handleLoadConversation(conv.id)}
              >
                <div className="truncate flex-1">
                  <div className="font-medium text-xs truncate">{conv.title}</div>
                  <div className="text-xs text-gray-400">
                    {new Date(conv.updatedAt).toLocaleDateString()} · {conv.messageCount} msgs
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteConversation(conv.id);
                  }}
                  className="text-gray-400 hover:text-red-500 text-xs ml-2 shrink-0"
                >
                  🗑
                </button>
              </div>
            ))}
            {conversations.length === 0 && (
              <div className="text-xs text-gray-400 text-center py-4">No conversations yet</div>
            )}
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b px-4 py-2 flex items-center gap-3">
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="text-gray-500 hover:text-gray-700"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          )}
          <h1 className="text-sm font-semibold">AI Chat</h1>

          {/* MCP server selector */}
          <label className="ml-2 flex items-center gap-1 text-xs text-gray-500">
            Server
            <select
              value={server}
              onChange={(e) => handleServerChange(e.target.value)}
              className="border rounded px-1.5 py-0.5 text-xs bg-white"
              title="MCP server for tool calls"
            >
              {SERVERS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>

          <button
            onClick={handleNewChat}
            className="ml-auto text-xs text-blue-600 hover:underline"
          >
            New Chat
          </button>
        </div>

        {/* Error banner */}
        {(error || chatError) && (
          <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-700">
            {error || chatError?.message}
            <button onClick={() => setError(null)} className="ml-2 text-red-500 hover:text-red-700">
              Dismiss
            </button>
          </div>
        )}

        {/* Messages */}
        <MessageList messages={messages as unknown as any[]} loading={loading} server={server} />

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={loading} />
      </div>
    </div>
  );
}
