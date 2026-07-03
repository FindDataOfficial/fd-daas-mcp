// @ts-nocheck — sql.js has no built-in types
// Schema managed by mcp/models/models.py — no CREATE TABLE here.
import initSqlJs from 'sql.js';
import fs from 'fs';
import path from 'path';
import { REPO_ROOT } from './paths';

// Resolve DAAS_DATABASE_URL against the repo root (located by findRepoRoot in
// paths.ts — NOT process.cwd(), which is only `dashboard/` when the server is
// launched from there). Mirrors daas-mcp's _resolve_url so a repo-relative
// value like `sqlite:///mcp/daas.db` resolves identically for the dashboard
// (sql.js reads) and the daas-mcp writer (spawned via `uv run --directory
// mcp/daas-mcp`, whose cwd is mcp/daas-mcp/ — not the repo root).

function resolveDaasDbPath(): string {
  const envRel = process.env.DAAS_DATABASE_URL?.replace('sqlite:///', '');
  if (envRel) {
    if (envRel === ':memory:') return envRel;
    return path.isAbsolute(envRel) ? envRel : path.resolve(REPO_ROOT, envRel);
  }
  return path.join(REPO_ROOT, 'mcp', 'daas.db');
}

const DB_PATH = resolveDaasDbPath();
export const DAAS_DB_PATH = DB_PATH;
const DB_DIR = path.dirname(DB_PATH);

let SQL = null;

async function getSql() {
  if (SQL) return SQL;
  SQL = await initSqlJs();
  return SQL;
}

const dbCache = new Map();

export async function getDb(name) {
  if (dbCache.has(name)) return dbCache.get(name);

  const sql = await getSql();
  const dbPath = name.endsWith('.db') ? path.join(DB_DIR, name) : DB_PATH;

  if (!fs.existsSync(dbPath)) {
    const db = new sql.Database();
    dbCache.set(name, db);
    return db;
  }

  const buffer = fs.readFileSync(dbPath);
  const db = new sql.Database(buffer);
  dbCache.set(name, db);
  return db;
}

export function saveDb(name) {
  const db = dbCache.get(name);
  if (!db) return;
  const data = db.export();
  const dbPath = name.endsWith('.db') ? path.join(DB_DIR, name) : DB_PATH;
  fs.writeFileSync(dbPath, Buffer.from(data));
}

export async function saveDashboardDb() {
  saveDb('dashboard');
}

export async function getDashboardDb() {
  return getDb('dashboard');
}

export function queryAll(db, sql, params = []) {
  const stmt = db.prepare(sql);
  if (params.length) stmt.bind(params);
  const rows = [];
  while (stmt.step()) {
    rows.push(stmt.getAsObject());
  }
  stmt.free();
  return rows;
}

export function getTableColumns(db, tableName) {
  const rows = queryAll(db, `PRAGMA table_info("${tableName}")`);
  return rows;
}

export function listTables(db) {
  const rows = queryAll(db, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name");
  return rows.map(r => String(r.name));
}

/**
 * Drop the cached sql.js DB for `name` so the next getDb() re-reads the file.
 * Call after any out-of-process write (e.g. our Python writer CLIs).
 */
export function invalidateDb(name) {
  const cached = dbCache.get(name);
  if (cached) {
    try { cached.close(); } catch {}
    dbCache.delete(name);
  }
}
