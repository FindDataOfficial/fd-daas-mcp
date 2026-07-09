'use client';

import ReasoningBlock from './reasoning-block';
import ToolCallCard from './tool-call-card';
import EchartsBlock from './echarts-block';
import UiResourceBlock from './ui-resource-block';

// Simple markdown-to-HTML renderer (ponytail: regex-based, replace with react-markdown if needed)
function renderMarkdown(text: string): string {
  let html = text
    // Escape HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono">$1</code>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-3 mb-1">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold mt-4 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-4 mb-2">$1</h1>')
    // Lists
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
    // Line breaks
    .replace(/\n\n/g, '</p><p class="mb-2">')
    .replace(/\n/g, '<br/>');

  return `<p class="mb-2">${html}</p>`;
}

// Extract ```echarts blocks from text
function parseEchartsBlocks(text: string): Array<{ type: 'text' | 'echarts'; content: string }> {
  const parts: Array<{ type: 'text' | 'echarts'; content: string }> = [];
  const regex = /```echarts\n([\s\S]*?)```/g;
  let lastIdx = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push({ type: 'text', content: text.slice(lastIdx, match.index) });
    }
    parts.push({ type: 'echarts', content: match[1].trim() });
    lastIdx = match.index + match[0].length;
  }

  if (lastIdx < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIdx) });
  }

  return parts.length > 0 ? parts : [{ type: 'text', content: text }];
}

interface MessagePart {
  type: string;
  text?: string;
  toolName?: string;
  toolCallId?: string;
  args?: Record<string, unknown>;
  // AI SDK v5 names the tool-result payload `output`; older previews used
  // `result`. Accept either so mcp-ui resource detection is robust to drift.
  input?: Record<string, unknown>;
  output?: unknown;
  result?: unknown;
  errorText?: string;
  state?: string;
}

interface Props {
  role: 'user' | 'assistant';
  parts: MessagePart[];
  server?: string;
}

// Extract _meta.ui.resourceUri from a tool-result payload (v5 `output` or
// legacy `result`). Returns null when the tool didn't return a UI resource.
function extractUiResourceUri(part: MessagePart): string | null {
  const payload = (part.output ?? part.result) as
    | { _meta?: { ui?: { resourceUri?: string } } }
    | undefined;
  const uri = payload?._meta?.ui?.resourceUri;
  return typeof uri === 'string' && uri.startsWith('ui://') ? uri : null;
}

export default function MessageBubble({ role, parts, server }: Props) {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white border text-gray-800'
        }`}
      >
        {parts.map((part, i) => {
          switch (part.type) {
            case 'text': {
              if (!part.text) return null;
              const segments = parseEchartsBlocks(part.text);
              return (
                <div key={i}>
                  {segments.map((seg, j) =>
                    seg.type === 'echarts' ? (
                      <EchartsBlock key={j} json={seg.content} />
                    ) : (
                      <div
                        key={j}
                        className={`text-sm leading-relaxed ${isUser ? 'text-white' : ''}`}
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(seg.content) }}
                      />
                    )
                  )}
                </div>
              );
            }

            case 'reasoning': {
              return <ReasoningBlock key={i} text={part.text || ''} />;
            }

            case 'tool-call': {
              return (
                <ToolCallCard
                  key={i}
                  toolName={part.toolName || 'unknown'}
                  args={part.args || {}}
                  state="call"
                />
              );
            }

            case 'tool-result': {
              const uiUri = extractUiResourceUri(part);
              if (uiUri) {
                return (
                  <UiResourceBlock
                    key={i}
                    server={server || 'composite-mcp'}
                    toolName={part.toolName || 'unknown'}
                    toolResourceUri={uiUri}
                    toolInput={(part.input ?? part.args) as Record<string, unknown> | undefined}
                    toolResult={part.output ?? part.result}
                  />
                );
              }
              return (
                <ToolCallCard
                  key={i}
                  toolName={part.toolName || 'unknown'}
                  args={part.args || {}}
                  result={part.result ?? part.output}
                  error={part.errorText}
                  state={part.errorText ? 'error' : 'result'}
                />
              );
            }

            default:
              return null;
          }
        })}
      </div>
    </div>
  );
}
