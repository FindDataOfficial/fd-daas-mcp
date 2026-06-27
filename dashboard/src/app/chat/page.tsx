'use client';

import { useState, useCallback } from 'react';
import { useChat } from '@ai-sdk/react';
import { TextStreamChatTransport } from 'ai';
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

export default function ChatPage() {
  const [conversationId, setConversationId] = useState<string>(() => generateId());
  const [conversations, setConversations] = useState<ChatConversation[]>(() => loadConversations());
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initialMessages = getConversation(conversationId);

  const {
    messages,
    sendMessage,
    status,
    error: chatError,
    setMessages,
  } = useChat({
    id: conversationId,
    transport: new TextStreamChatTransport({ api: '/api/chat' }),
    onError: (err) => {
      setError(err.message);
    },
  });

  const loading = status === 'submitted' || status === 'streaming';

  // Persist messages on change
  const handleSend = useCallback(
    (text: string) => {
      setError(null);
      sendMessage({ text });
    },
    [sendMessage]
  );

  // Save conversation when messages change (debounced by effect in real impl)
  if (messages.length > 0) {
    // pony tail: save on every render when messages change, fine for local use
    saveConversation(conversationId, messages);
  }

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
        <MessageList messages={messages} loading={loading} />

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={loading} />
      </div>
    </div>
  );
}
