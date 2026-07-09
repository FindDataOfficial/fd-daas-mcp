// @ts-nocheck — joins return loose shapes; we cast at the boundary
// Indicator-score + indicator-collection read helpers for the /process/indicators
// workspace and the /process/indicators/collections page. All queries go
// through sql.js (read-only WASM) against `mcp/daas.db`. Writes go through
// `/api/indicators/*` which calls the Python writer CLI (collection_writer.py
// indicator subcommands).
//
// Effective score for an indicator in a collection is a 3-level chain:
//   COALESCE(item.score, indicator_rules.score, sources.score) → NULL
// (item override → indicator default → datasource default).

import { getDb, queryAll, invalidateDb } from './db';
import type {
  IndicatorScoreRow,
  IndicatorCollectionSummary,
  IndicatorCollectionDetail,
  IndicatorCollectionScoreItem,
  IndicatorCollectionChangeRow,
} from './schema';

const DAAS_DB = 'daas.db';

export function refreshDaasDb() {
  invalidateDb(DAAS_DB);
}

function toNum(v: unknown): number | null {
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * Every indicator rule with its raw `score`, the datasource's default score,
 * and the resolved `effective_default_score` = COALESCE(indicator.score, sources.score).
 * LEFT JOINs `sources` on the indicator's `datasource` (soft ref). Also pulls
 * the latest observation value+date for display.
 */
export async function loadIndicatorScores(): Promise<IndicatorScoreRow[]> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const rows = queryAll(
    db,
    `SELECT i.id, i.name, i.datasource, i.function_name, i.op, i.value_column,
            i.indicator_name, i.enabled, i.score,
            s.score AS datasource_default_score,
            COALESCE(i.score, s.score) AS effective_default_score,
            (SELECT o.value FROM observations o
               WHERE o.source = i.datasource
                 AND o.function_name = i.function_name
                 AND o.indicator = i.indicator_name
               ORDER BY o.date DESC LIMIT 1) AS latest_value,
            (SELECT o.date FROM observations o
               WHERE o.source = i.datasource
                 AND o.function_name = i.function_name
                 AND o.indicator = i.indicator_name
               ORDER BY o.date DESC LIMIT 1) AS latest_date
       FROM indicator_rules i
       LEFT JOIN sources s ON s.name = i.datasource
      ORDER BY i.created_at DESC, i.id DESC`,
  );
  return rows.map((r) => ({
    id: Number(r.id),
    name: String(r.name),
    datasource: r.datasource ?? null,
    function_name: r.function_name ?? null,
    op: r.op ?? null,
    value_column: r.value_column ?? null,
    indicator_name: r.indicator_name ?? null,
    enabled: Boolean(r.enabled),
    score: toNum(r.score),
    datasource_default_score: toNum(r.datasource_default_score),
    effective_default_score: toNum(r.effective_default_score),
    latest_value: r.latest_value ?? null,
    latest_date: r.latest_date ?? null,
  }));
}

/** All indicator collections, each with its current item count. */
export async function loadIndicatorCollections(): Promise<IndicatorCollectionSummary[]> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const rows = queryAll(
    db,
    `SELECT c.id, c.name, c.description, c.created_at, c.updated_at,
            (SELECT count(*) FROM indicator_collection_items i WHERE i.collection_id = c.id) AS item_count
       FROM indicator_collections c
      ORDER BY c.name ASC`,
  );
  return rows.map((r) => ({
    id: Number(r.id),
    name: String(r.name),
    description: r.description ?? null,
    item_count: Number(r.item_count ?? 0),
    created_at: r.created_at ?? null,
    updated_at: r.updated_at ?? null,
  }));
}

/**
 * One indicator collection + its items (ordered by sort_order), each with the
 * 3-level resolved effective score + raw item/indicator/datasource scores.
 * Returns null if the collection doesn't exist.
 */
export async function loadIndicatorCollectionDetail(
  name: string,
): Promise<IndicatorCollectionDetail | null> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const colls = queryAll(
    db,
    `SELECT id, name, description, created_at, updated_at
       FROM indicator_collections
      WHERE name = ?
      LIMIT 1`,
    [name],
  );
  if (colls.length === 0) return null;
  const c = colls[0];
  const items = queryAll(
    db,
    `SELECT i.id AS item_id, i.indicator_id, i.sort_order, i.score AS item_score,
            ir.name AS indicator_name, ir.score AS indicator_default_score, ir.datasource,
            s.score AS source_default_score
       FROM indicator_collection_items i
       JOIN indicator_rules ir ON ir.id = i.indicator_id
       LEFT JOIN sources s ON s.name = ir.datasource
      WHERE i.collection_id = ?
      ORDER BY i.sort_order, i.id`,
    [Number(c.id)],
  );
  const mapped: IndicatorCollectionScoreItem[] = items.map((r) => {
    const itemScore = toNum(r.item_score);
    const indScore = toNum(r.indicator_default_score);
    const srcScore = toNum(r.source_default_score);
    // 3-level resolution: item override → indicator default → datasource default.
    const resolved = itemScore ?? indScore ?? srcScore;
    return {
      item_id: Number(r.item_id),
      indicator_id: Number(r.indicator_id),
      indicator_name: String(r.indicator_name ?? ''),
      sort_order: Number(r.sort_order ?? 0),
      item_score: itemScore,
      indicator_default_score: indScore,
      source_default_score: srcScore,
      score: resolved,
    };
  });
  return {
    id: Number(c.id),
    name: String(c.name),
    description: c.description ?? null,
    created_at: c.created_at ?? null,
    updated_at: c.updated_at ?? null,
    items: mapped,
  };
}

/**
 * Audit-log rows for an indicator collection (or all collections when `name`
 * is null), newest first. Each row is enriched with the collection name.
 */
export async function loadIndicatorCollectionHistory(
  name: string | null,
  action?: 'add_in' | 'remove_out' | null,
  limit = 100,
): Promise<IndicatorCollectionChangeRow[]> {
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
            ch.indicator_name, ch.action, ch.source, ch.reason, ch.changed_at
       FROM indicator_collection_changes ch
       JOIN indicator_collections c ON c.id = ch.collection_id
      ${whereSql}
      ORDER BY ch.changed_at DESC, ch.id DESC
      LIMIT ?`,
    params,
  );
  return rows.map((r) => ({
    id: Number(r.id),
    collection_id: Number(r.collection_id),
    collection_name: r.collection_name ?? null,
    indicator_name: String(r.indicator_name ?? ''),
    action: String(r.action) as 'add_in' | 'remove_out',
    source: String(r.source) as 'manual' | 'cron',
    reason: r.reason ?? null,
    changed_at: r.changed_at ?? null,
  }));
}

/** All indicator rule names (for the "Add indicator" picker on the detail page). */
export async function listIndicatorNames(): Promise<{ id: number; name: string }[]> {
  invalidateDb(DAAS_DB);
  const db = await getDb(DAAS_DB);
  const rows = queryAll(
    db,
    `SELECT id, name FROM indicator_rules ORDER BY name ASC`,
  );
  return rows.map((r) => ({ id: Number(r.id), name: String(r.name) }));
}
