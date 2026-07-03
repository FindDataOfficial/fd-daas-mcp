'use client';

import { useMemo, useState } from 'react';
import { useDraggable } from '@dnd-kit/core';
import type { CatalogGroup, CatalogSource, CatalogSection } from '@/lib/schema';

interface Props {
  groups: CatalogGroup[];
}

type DragPayload =
  | { kind: 'source'; source_name: string }
  | { kind: 'section'; source_name: string; section_name: string };

function encodePayload(p: DragPayload): string {
  return JSON.stringify(p);
}

function DraggableNode({
  id,
  payload,
  children,
}: {
  id: string;
  payload: DragPayload;
  children: React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id,
    data: payload,
  });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={`cursor-grab active:cursor-grabbing select-none ${
        isDragging ? 'opacity-40' : ''
      }`}
      data-drag-payload={encodePayload(payload)}
    >
      {children}
    </div>
  );
}

function matchesQuery(
  src: CatalogSource,
  q: string,
): { hit: boolean; sectionHits: Set<number> } {
  if (!q) return { hit: true, sectionHits: new Set() };
  const lower = q.toLowerCase();
  let hit = false;
  if (src.name.toLowerCase().includes(lower)) hit = true;
  if (src.label.toLowerCase().includes(lower)) hit = true;
  const sectionHits = new Set<number>();
  for (const f of src.forms) {
    if (f.form_type.toLowerCase().includes(lower)) hit = true;
    if (f.label && f.label.toLowerCase().includes(lower)) hit = true;
    for (const s of f.sections) {
      if (
        s.section_name.toLowerCase().includes(lower) ||
        (s.instruction ?? '').toLowerCase().includes(lower)
      ) {
        sectionHits.add(s.id);
        hit = true;
      }
    }
  }
  return { hit, sectionHits };
}

export default function CatalogPane({ groups }: Props) {
  const [query, setQuery] = useState('');
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [expandedSources, setExpandedSources] = useState<Record<number, boolean>>({});

  const filtered = useMemo(() => {
    if (!query) return groups;
    const out: CatalogGroup[] = [];
    for (const g of groups) {
      const keepSrcs = g.sources.filter((s) => matchesQuery(s, query).hit);
      if (keepSrcs.length) out.push({ ...g, sources: keepSrcs });
    }
    return out;
  }, [groups, query]);

  return (
    <div className="h-full flex flex-col bg-gray-50 border-r overflow-hidden">
      <div className="p-3 border-b bg-white">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search datasources, forms, sections…"
          className="w-full text-sm border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {filtered.length === 0 && (
          <div className="text-xs text-gray-400 text-center py-6">No datasources match.</div>
        )}
        {filtered.map((g) => {
          const key = g.category_id == null ? 'null' : String(g.category_id);
          const isOpen = !collapsed[key];
          return (
            <div key={key} className="mb-3">
              <button
                onClick={() => setCollapsed((c) => ({ ...c, [key]: !c[key] }))}
                className="w-full text-left text-xs font-semibold text-gray-600 uppercase tracking-wide px-2 py-1 hover:bg-gray-100 rounded flex items-center"
              >
                <span className="w-3 text-gray-400">{isOpen ? '▾' : '▸'}</span>
                <span className="ml-1">{g.category_name}</span>
                <span className="ml-auto text-gray-400">{g.sources.length}</span>
              </button>
              {isOpen && (
                <ul className="mt-1 space-y-0.5">
                  {g.sources.map((src) => {
                    const { sectionHits } = matchesQuery(src, query);
                    const expanded = expandedSources[src.id];
                    return (
                      <li key={src.id}>
                        <div className="flex items-center gap-1 px-1">
                          <button
                            onClick={() =>
                              setExpandedSources((e) => ({ ...e, [src.id]: !e[src.id] }))
                            }
                            className="text-gray-400 hover:text-gray-700 w-4 text-xs"
                            aria-label="Toggle sections"
                            disabled={!src.forms.length}
                          >
                            {src.forms.length ? (expanded ? '▾' : '▸') : ' '}
                          </button>
                          <DraggableNode
                            id={`source:${src.name}`}
                            payload={{ kind: 'source', source_name: src.name }}
                          >
                            <div className="text-sm bg-white border rounded px-2 py-1 hover:bg-blue-50 hover:border-blue-300 flex items-baseline gap-2">
                              <span className="font-medium">{src.name}</span>
                              <span className="text-xs text-gray-500 truncate">{src.label}</span>
                            </div>
                          </DraggableNode>
                        </div>
                        {expanded && src.forms.length > 0 && (
                          <ul className="ml-6 mt-0.5 space-y-0.5">
                            {src.forms.map((f) => (
                              <li key={f.id}>
                                <div className="text-xs text-gray-500 px-1 py-0.5">
                                  {f.form_type}
                                  {f.label && <span className="text-gray-400"> · {f.label}</span>}
                                </div>
                                <ul className="ml-3 space-y-0.5">
                                  {f.sections.map((s: CatalogSection) => (
                                    <li key={s.id}>
                                      <DraggableNode
                                        id={`section:${src.name}:${s.section_name}`}
                                        payload={{
                                          kind: 'section',
                                          source_name: src.name,
                                          section_name: s.section_name,
                                        }}
                                      >
                                        <div
                                          className={`text-xs border rounded px-2 py-0.5 hover:bg-blue-50 hover:border-blue-300 ${
                                            sectionHits.has(s.id)
                                              ? 'bg-yellow-50 border-yellow-300'
                                              : 'bg-white'
                                          }`}
                                        >
                                          {s.section_name}
                                        </div>
                                      </DraggableNode>
                                    </li>
                                  ))}
                                </ul>
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
