'use client';

import { useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { CollectionItem } from '@/lib/schema';

interface Props {
  collectionName: string;
  items: CollectionItem[];
  onRemove: (item: CollectionItem) => Promise<void>;
  error?: string | null;
  onClearError?: () => void;
}

function ItemCard({
  item,
  onRemove,
  onExpand,
  expanded,
}: {
  item: CollectionItem;
  onRemove: () => void;
  onExpand: () => void;
  expanded: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `item:${item.item_id}`,
    data: { kind: 'item', item_id: item.item_id },
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <li
      ref={setNodeRef}
      style={style}
      className="bg-white border rounded-md shadow-sm overflow-hidden"
    >
      <div className="flex items-center gap-2 px-2 py-1.5">
        <button
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing text-gray-400 hover:text-gray-700 px-1"
          aria-label="Drag to reorder"
        >
          ⋮⋮
        </button>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium truncate">
            {item.source_name}
            {item.section_name && (
              <span className="text-gray-500 font-normal"> · {item.section_name}</span>
            )}
          </div>
          <div className="text-xs text-gray-500 truncate">
            {item.source_label}
            {item.form_type && ` · ${item.form_type}`}
          </div>
        </div>
        {item.instruction && (
          <button
            onClick={onExpand}
            className="text-xs text-gray-400 hover:text-gray-700"
            aria-label="Toggle instruction"
          >
            {expanded ? '▾' : '▸'}
          </button>
        )}
        <button
          onClick={onRemove}
          className="text-gray-400 hover:text-red-500 text-sm px-1"
          aria-label="Remove from collection"
        >
          ×
        </button>
      </div>
      {expanded && item.instruction && (
        <div className="px-3 pb-2 text-xs text-gray-600 bg-gray-50 border-t whitespace-pre-wrap">
          {item.instruction}
        </div>
      )}
    </li>
  );
}

function DropZone({ children, empty }: { children: React.ReactNode; empty: boolean }) {
  const { setNodeRef, isOver } = useDroppable({ id: 'collection-dropzone' });
  return (
    <div
      ref={setNodeRef}
      className={`flex-1 overflow-y-auto p-3 ${
        isOver ? 'bg-blue-50' : empty ? 'bg-gray-50' : 'bg-white'
      }`}
    >
      {children}
    </div>
  );
}

export default function CollectionPane({
  collectionName,
  items,
  onRemove,
  error,
  onClearError,
}: Props) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b bg-white">
        <div className="text-sm font-semibold">{collectionName}</div>
        <div className="text-xs text-gray-500">
          {items.length} item{items.length === 1 ? '' : 's'}
        </div>
      </div>
      {error && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-xs text-red-700 flex items-start gap-2">
          <span className="flex-1">{error}</span>
          {onClearError && (
            <button onClick={onClearError} className="text-red-500 hover:text-red-700">×</button>
          )}
        </div>
      )}
      <SortableContext
        items={items.map((i) => `item:${i.item_id}`)}
        strategy={verticalListSortingStrategy}
      >
        <DropZone empty={items.length === 0}>
          {items.length === 0 ? (
            <div className="h-full flex items-center justify-center text-sm text-gray-400 text-center px-6">
              Drop a datasource or section here to add it to <b className="mx-1">{collectionName}</b>.
            </div>
          ) : (
            <ul className="space-y-1.5">
              {items.map((it) => (
                <ItemCard
                  key={it.item_id}
                  item={it}
                  expanded={!!expanded[it.item_id]}
                  onExpand={() =>
                    setExpanded((e) => ({ ...e, [it.item_id]: !e[it.item_id] }))
                  }
                  onRemove={() => onRemove(it)}
                />
              ))}
            </ul>
          )}
        </DropZone>
      </SortableContext>
    </div>
  );
}
