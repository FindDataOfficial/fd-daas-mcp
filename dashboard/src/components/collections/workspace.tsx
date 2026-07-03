'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  DndContext,
  closestCenter,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { arrayMove, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import CatalogPane from './catalog-pane';
import CollectionPane from './collection-pane';
import ChatPane from './chat-pane';
import CollectionSwitcher from './collection-switcher';
import type { CatalogGroup, CollectionDetail, CollectionItem } from '@/lib/schema';

interface CollectionSummary {
  id: number;
  name: string;
  item_count: number;
}

interface Props {
  catalog: CatalogGroup[];
  collection: CollectionDetail;
  collections: CollectionSummary[];
}

export default function CollectionWorkspace({ catalog, collection, collections }: Props) {
  const router = useRouter();
  const [items, setItems] = useState<CollectionItem[]>(collection.items);
  const [error, setError] = useState<string | null>(null);

  // If parent (server) reloads with a different items list (e.g. after navigation), sync.
  if (
    items.length !== collection.items.length ||
    items.some((it, i) => it.item_id !== collection.items[i]?.item_id)
  ) {
    setItems(collection.items);
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  async function refresh() {
    // Use Next router refresh to re-run the server component with fresh DB read.
    router.refresh();
  }

  async function handleAdd(source_name: string, section_name: string | null) {
    setError(null);
    const res = await fetch(
      `/api/collections/${encodeURIComponent(collection.name)}/items`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_name, section_name }),
      },
    );
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body?.error ?? `HTTP ${res.status}`);
      return;
    }
    await refresh();
  }

  async function handleRemove(item: CollectionItem) {
    setError(null);
    const res = await fetch(
      `/api/collections/${encodeURIComponent(collection.name)}/items`,
      {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_name: item.source_name,
          section_name: item.section_name,
        }),
      },
    );
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body?.error ?? `HTTP ${res.status}`);
      return;
    }
    await refresh();
  }

  async function handleReorder(newOrder: number[]) {
    setError(null);
    const res = await fetch(
      `/api/collections/${encodeURIComponent(collection.name)}/items`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ordered_item_ids: newOrder }),
      },
    );
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body?.error ?? `HTTP ${res.status}`);
      await refresh(); // re-sync from server
      return;
    }
    // Server is now in sync; no need to refresh — local state already updated.
  }

  function handleDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over) return;
    const activeId = String(active.id);
    const overId = String(over.id);
    const payload = active.data.current as
      | { kind: 'source'; source_name: string }
      | { kind: 'section'; source_name: string; section_name: string }
      | { kind: 'item'; item_id: number }
      | undefined;

    // Catalog → collection drop
    if (payload && (payload.kind === 'source' || payload.kind === 'section')) {
      handleAdd(
        payload.source_name,
        payload.kind === 'section' ? payload.section_name : null,
      );
      return;
    }

    // Intra-pane reorder
    if (activeId.startsWith('item:') && overId.startsWith('item:') && activeId !== overId) {
      const oldIdx = items.findIndex((i) => `item:${i.item_id}` === activeId);
      const newIdx = items.findIndex((i) => `item:${i.item_id}` === overId);
      if (oldIdx < 0 || newIdx < 0) return;
      const reordered = arrayMove(items, oldIdx, newIdx);
      setItems(reordered); // optimistic
      handleReorder(reordered.map((i) => i.item_id));
    }
  }

  return (
    <div className="h-full flex flex-col">
      <CollectionSwitcher collections={collections} activeName={collection.name} />
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <div className="flex-1 grid grid-cols-[280px_minmax(0,1fr)_360px] overflow-hidden">
          <CatalogPane groups={catalog} />
          <CollectionPane
            collectionName={collection.name}
            items={items}
            onRemove={handleRemove}
            error={error}
            onClearError={() => setError(null)}
          />
          <ChatPane collectionName={collection.name} itemCount={items.length} />
        </div>
      </DndContext>
    </div>
  );
}
