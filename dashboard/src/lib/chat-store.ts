const STORAGE_PREFIX = 'mcp_chat_';
const MAX_MESSAGES = 50;
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

export interface ChatConversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

function storageKey(id: string): string {
  return `${STORAGE_PREFIX}${id}`;
}

function indexKey(): string {
  return `${STORAGE_PREFIX}index`;
}

function loadIndex(): ChatConversation[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(indexKey());
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveIndex(convs: ChatConversation[]): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(indexKey(), JSON.stringify(convs));
}

export function loadConversations(): ChatConversation[] {
  const index = loadIndex();
  // prune old conversations
  const now = Date.now();
  const valid = index.filter((c) => {
    const age = now - new Date(c.updatedAt).getTime();
    return age < MAX_AGE_MS;
  });
  if (valid.length !== index.length) {
    saveIndex(valid);
  }
  return valid.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
}

export function getConversation(id: string): any[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(storageKey(id));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveConversation(id: string, messages: any[], title?: string): void {
  if (typeof window === 'undefined') return;

  // Cap messages
  const capped = messages.length > MAX_MESSAGES
    ? messages.slice(messages.length - MAX_MESSAGES)
    : messages;

  localStorage.setItem(storageKey(id), JSON.stringify(capped));

  // Update index
  const index = loadIndex();
  const existing = index.findIndex((c) => c.id === id);
  const entry: ChatConversation = {
    id,
    title: title || `Chat ${id.slice(0, 6)}`,
    createdAt: existing >= 0 ? index[existing].createdAt : new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messageCount: capped.length,
  };

  if (existing >= 0) {
    index[existing] = entry;
  } else {
    index.push(entry);
  }

  saveIndex(index);
}

export function deleteConversation(id: string): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(storageKey(id));
  const index = loadIndex().filter((c) => c.id !== id);
  saveIndex(index);
}

export function generateId(): string {
  return crypto.randomUUID();
}
