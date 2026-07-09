// @ts-nocheck — joins return loose shapes; we cast at the boundary
// Score read helpers for the /scores dashboard page. Reads go through sql.js
// (read-only WASM) against `mcp/daas.db`, the same path as the collections
// workspace. Writes go through `/api/scores/*` → collection_writer.py.

import { getDb, queryAll, invalidateDb } from './db';
import type { SourceScoreRow, CollectionScoreItem } from './schema';

const DAAS_DB = 'daas.db'; // anchors getDb() to mcp/daas.db

/** Every datasource with its default `score`. For the /scores default-score table. */
export async function loadSourceScores(): Promise<SourceScoreRow[]> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const rows = queryAll(db, `
    SELECT id, name, label, description, score
      FROM sources
     ORDER BY name
  `);
  return rows.map((r) => ({
    id: Number(r.id),
    name: String(r.name),
    label: String(r.label),
    description: r.description ?? null,
    score: r.score == null ? null : Number(r.score),
  }));
}

/**
 * One collection's items with per-item score override + the datasource's
 * default score + the resolved effective score. Ordered by sort_order.
 * Returns null if the collection doesn't exist.
 */
export async function loadCollectionScores(
  name: string,
): Promise<{ id: number; name: string; items: CollectionScoreItem[] } | null> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);

  const coll = queryAll(
    db,
    `SELECT id, name FROM datasource_collections WHERE name = ?`,
    [name],
  )[0];
  if (!coll) return null;

  const items = queryAll(db, `
    SELECT i.id AS item_id,
           i.source_id, i.section_id, i.sort_order,
           i.score AS item_score,
           s.name AS source_name, s.label AS source_label,
           s.score AS source_default_score,
           sec.section_name AS section_name
      FROM datasource_collection_items i
      JOIN sources s ON s.id = i.source_id
      LEFT JOIN datasource_sections sec ON sec.id = i.section_id
     WHERE i.collection_id = ?
     ORDER BY i.sort_order, i.id
  `, [Number(coll.id)]);

  const mapped: CollectionScoreItem[] = items.map((r) => {
    const itemScore = r.item_score == null ? null : Number(r.item_score);
    const sourceDefaultScore =
      r.source_default_score == null ? null : Number(r.source_default_score);
    return {
      item_id: Number(r.item_id),
      source_id: Number(r.source_id),
      source_name: String(r.source_name),
      source_label: String(r.source_label),
      section_id: r.section_id == null ? null : Number(r.section_id),
      section_name: r.section_name ?? null,
      sort_order: Number(r.sort_order ?? 0),
      item_score: itemScore,
      source_default_score: sourceDefaultScore,
      score: itemScore != null ? itemScore : sourceDefaultScore,
    };
  });

  return { id: Number(coll.id), name: String(coll.name), items: mapped };
}
