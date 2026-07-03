// @ts-nocheck — joins return loose shapes; we cast at the boundary
// Catalog / collection / collections read helpers for the collections workspace.
// All queries go through sql.js (read-only WASM) against `mcp/daas.db`.
// Writes go through `/api/collections/*` which calls the Python writer CLI.

import { getDb, queryAll, invalidateDb } from './db';
import type {
  CatalogGroup,
  CatalogSource,
  CatalogForm,
  CatalogSection,
  CollectionDetail,
  CollectionItem,
  DatasourceCollectionRow,
} from './schema';

const DAAS_DB = 'daas.db'; // anchors getDb() to mcp/daas.db

export function refreshDaasDb() {
  invalidateDb(DAAS_DB);
}

/**
 * All datasources, grouped by category, with nested forms/sections. Used by
 * the catalog (left) pane. Uncategorized sources fall under `category_id=null`.
 */
export async function loadCatalog(): Promise<CatalogGroup[]> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);

  const sources = queryAll(db, `
    SELECT s.id, s.name, s.label, s.description, s.category_id,
           c.name AS category_name
      FROM sources s
      LEFT JOIN categories c ON c.id = s.category_id
     WHERE s.enabled = 1
     ORDER BY COALESCE(c.name, '~zzzzz'), s.name
  `);

  if (sources.length === 0) return [];

  const sourceIds = sources.map((r) => r.id);
  const idList = sourceIds.join(',');

  const forms = sourceIds.length
    ? queryAll(db, `
        SELECT id, source_id, form_type, label
          FROM datasource_forms
         WHERE source_id IN (${idList})
         ORDER BY source_id, form_type
      `)
    : [];

  const formIds = forms.map((r) => r.id);
  const sections = formIds.length
    ? queryAll(db, `
        SELECT id, form_id, section_name, instruction
          FROM datasource_sections
         WHERE form_id IN (${formIds.join(',')})
         ORDER BY form_id, COALESCE(sort_order, 999999), section_name
      `)
    : [];

  const sectionsByForm = new Map<number, CatalogSection[]>();
  for (const s of sections) {
    const arr = sectionsByForm.get(s.form_id) ?? [];
    arr.push({
      id: s.id,
      section_name: String(s.section_name),
      instruction: s.instruction ?? null,
    });
    sectionsByForm.set(s.form_id, arr);
  }

  const formsBySource = new Map<number, CatalogForm[]>();
  for (const f of forms) {
    const arr = formsBySource.get(f.source_id) ?? [];
    arr.push({
      id: f.id,
      form_type: String(f.form_type),
      label: f.label ?? null,
      sections: sectionsByForm.get(f.id) ?? [],
    });
    formsBySource.set(f.source_id, arr);
  }

  // Group sources by category. Stable key = category_id (null bucket separate).
  const groups = new Map<string, CatalogGroup>();
  for (const s of sources) {
    const key = s.category_id == null ? 'null' : String(s.category_id);
    if (!groups.has(key)) {
      groups.set(key, {
        category_id: s.category_id == null ? null : Number(s.category_id),
        category_name: s.category_name ?? '(uncategorized)',
        sources: [],
      });
    }
    const src: CatalogSource = {
      id: Number(s.id),
      name: String(s.name),
      label: String(s.label),
      description: s.description ?? null,
      category_id: s.category_id == null ? null : Number(s.category_id),
      category_name: s.category_name ?? null,
      forms: formsBySource.get(s.id) ?? [],
    };
    groups.get(key)!.sources.push(src);
  }

  return Array.from(groups.values());
}

/** Every collection (id, name, description, item_count). For the picker. */
export async function loadCollections(): Promise<
  Array<DatasourceCollectionRow & { item_count: number }>
> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const rows = queryAll(db, `
    SELECT c.id, c.name, c.description, c.created_at, c.updated_at,
           (SELECT COUNT(*) FROM datasource_collection_items i
             WHERE i.collection_id = c.id) AS item_count
      FROM datasource_collections c
     ORDER BY c.name
  `);
  return rows.map((r) => ({
    id: Number(r.id),
    name: String(r.name),
    description: r.description ?? null,
    created_at: String(r.created_at ?? ''),
    updated_at: String(r.updated_at ?? ''),
    item_count: Number(r.item_count ?? 0),
  }));
}

/**
 * One collection's items, resolved to source / form / section / instruction,
 * ordered by sort_order. Returns null if the collection doesn't exist.
 */
export async function loadCollection(name: string): Promise<CollectionDetail | null> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);

  const coll = queryAll(db, `
    SELECT id, name, description
      FROM datasource_collections
     WHERE name = ?
  `, [name])[0];
  if (!coll) return null;

  const items = queryAll(db, `
    SELECT i.id AS item_id,
           i.source_id, i.section_id, i.sort_order,
           s.name AS source_name, s.label AS source_label,
           sec.section_name AS section_name,
           sec.instruction AS instruction,
           f.form_type AS form_type
      FROM datasource_collection_items i
      JOIN sources s ON s.id = i.source_id
      LEFT JOIN datasource_sections sec ON sec.id = i.section_id
      LEFT JOIN datasource_forms f ON f.id = sec.form_id
     WHERE i.collection_id = ?
     ORDER BY i.sort_order, i.id
  `, [Number(coll.id)]);

  const mapped: CollectionItem[] = items.map((r) => ({
    item_id: Number(r.item_id),
    source_id: Number(r.source_id),
    source_name: String(r.source_name),
    source_label: String(r.source_label),
    section_id: r.section_id == null ? null : Number(r.section_id),
    section_name: r.section_name ?? null,
    form_type: r.form_type ?? null,
    instruction: r.instruction ?? null,
    sort_order: Number(r.sort_order ?? 0),
  }));

  return {
    id: Number(coll.id),
    name: String(coll.name),
    description: coll.description ?? null,
    items: mapped,
  };
}
