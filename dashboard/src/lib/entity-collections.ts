// @ts-nocheck — joins return loose shapes; we cast at the boundary
// Entity-collection read helpers for the /entities workspace.
// All queries go through sql.js (read-only WASM) against `mcp/daas.db`.
// Writes go through `/api/entities/*` which calls the Python writer CLI
// (collection_writer.py entity-collection subcommands).

import { getDb, queryAll, invalidateDb } from './db';
import type {
  EntityCollectionRow,
  EntityCollectionDetail,
  EntityCollectionMemberRow,
  EntityCollectionChangeRow,
} from './schema';

const DAAS_DB = 'daas.db';

export function refreshDaasDb() {
  invalidateDb(DAAS_DB);
}

/**
 * Parse a sql.js `rule_json` value (stored as a JSON text blob) into an object
 * (or null). Returns null when the column is NULL or the string is empty.
 */
function parseRule(v: unknown): Record<string, any> | null {
  if (v == null) return null;
  if (typeof v === 'object') return v as Record<string, any>;
  const s = String(v).trim();
  if (!s) return null;
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

/** All entity collections, each with its current member count. */
export async function loadEntityCollections(): Promise<EntityCollectionRow[]> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const rows = queryAll(
    db,
    `SELECT c.id, c.name, c.description, c.rule_json, c.created_at, c.updated_at,
            (SELECT count(*) FROM entity_collection_items i WHERE i.collection_id = c.id) AS item_count
       FROM entity_collections c
      ORDER BY c.name ASC`,
  );
  return rows.map((r) => ({
    id: Number(r.id),
    name: String(r.name),
    description: r.description ?? null,
    rule: parseRule(r.rule_json),
    item_count: Number(r.item_count ?? 0),
    created_at: r.created_at ?? null,
    updated_at: r.updated_at ?? null,
  }));
}

/** One collection + its current members (ordered, joined with `entities`). */
export async function loadEntityCollectionDetail(
  name: string,
): Promise<EntityCollectionDetail | null> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const colls = queryAll(
    db,
    `SELECT id, name, description, rule_json, created_at, updated_at
       FROM entity_collections
      WHERE name = ?
      LIMIT 1`,
    [name],
  );
  if (colls.length === 0) return null;
  const c = colls[0];
  const members = queryAll(
    db,
    `SELECT i.id AS item_id, i.entity_id, i.sort_order, i.added_at, i.added_reason,
            e.entity_type, e.code, e.name, e.ticker, e.exchange, e.country_code
       FROM entity_collection_items i
       JOIN entities e ON e.id = i.entity_id
      WHERE i.collection_id = ?
      ORDER BY i.sort_order, i.id`,
    [Number(c.id)],
  );
  const mapped: EntityCollectionMemberRow[] = members.map((r) => ({
    item_id: Number(r.item_id),
    entity_id: Number(r.entity_id),
    sort_order: Number(r.sort_order ?? 0),
    added_at: r.added_at ?? null,
    added_reason: r.added_reason ?? null,
    entity_type: r.entity_type ?? null,
    code: r.code ?? null,
    name: r.name ?? null,
    ticker: r.ticker ?? null,
    exchange: r.exchange ?? null,
    country_code: r.country_code ?? null,
  }));
  return {
    id: Number(c.id),
    name: String(c.name),
    description: c.description ?? null,
    rule: parseRule(c.rule_json),
    created_at: c.created_at ?? null,
    updated_at: c.updated_at ?? null,
    members: mapped,
  };
}

/**
 * Audit-log rows for a collection (or all collections when `name` is null),
 * newest first. Each row is enriched with collection name + entity code/name.
 */
export async function loadEntityCollectionHistory(
  name: string | null,
  action?: 'add_in' | 'remove_out' | null,
  limit = 100,
): Promise<EntityCollectionChangeRow[]> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const params: any[] = [];
  const where: string[] = [];
  if (name) {
    params.push(name);
    where.push('c.name = ?');
  }
  if (action) {
    params.push(action);
    where.push('ch.action = ?');
  }
  const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';
  params.push(Math.min(Math.max(limit, 1), 500));
  const rows = queryAll(
    db,
    `SELECT ch.id, ch.collection_id, c.name AS collection_name,
            ch.entity_id, e.code AS entity_code, e.name AS entity_name,
            ch.action, ch.source, ch.reason, ch.changed_at
       FROM entity_collection_changes ch
       JOIN entity_collections c ON c.id = ch.collection_id
       LEFT JOIN entities e ON e.id = ch.entity_id
      ${whereSql}
      ORDER BY ch.changed_at DESC, ch.id DESC
      LIMIT ?`,
    params,
  );
  return rows.map((r) => ({
    id: Number(r.id),
    collection_id: Number(r.collection_id),
    collection_name: r.collection_name ?? null,
    entity_id: r.entity_id == null ? null : Number(r.entity_id),
    entity_code: r.entity_code ?? null,
    entity_name: r.entity_name ?? null,
    action: String(r.action),
    source: String(r.source),
    reason: r.reason ?? null,
    changed_at: r.changed_at ?? null,
  }));
}

/** Live entity search for the "Add member" picker (name / ticker / code / alias). */
export async function searchEntitiesForPicker(
  query: string,
  limit = 20,
): Promise<{ id: number; entity_type: string; code: string; name: string; ticker: string | null; exchange: string | null; country_code: string | null }[]> {
  if (!query.trim()) return [];
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const like = `%${query.toLowerCase()}%`;
  const rows = queryAll(
    db,
    `SELECT id, entity_type, code, name, ticker, exchange, country_code
       FROM entities
      WHERE LOWER(name) LIKE ? OR LOWER(ticker) LIKE ? OR LOWER(code) LIKE ?
      ORDER BY name ASC
      LIMIT ?`,
    [like, like, like, Math.min(Math.max(limit, 1), 100)],
  );
  return rows.map((r) => ({
    id: Number(r.id),
    entity_type: String(r.entity_type),
    code: String(r.code),
    name: String(r.name),
    ticker: r.ticker ?? null,
    exchange: r.exchange ?? null,
    country_code: r.country_code ?? null,
  }));
}
