// @ts-nocheck — sql.js has no built-in types
// Schema managed by mcp/models/models.py — no CREATE TABLE here.
import initSqlJs from 'sql.js';
import fs from 'fs';
import path from 'path';

const DB_PATH = process.env.DAAS_DATABASE_URL?.replace('sqlite:///', '')
  || path.join(process.cwd(), '..', 'mcp', 'daas.db');
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
