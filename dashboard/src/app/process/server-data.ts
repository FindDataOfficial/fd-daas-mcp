// @ts-nocheck
import { getDb, listTables, getTableColumns } from '@/lib/db';
import { callTool } from '@/lib/mcp-call';

/** scraw_* source tables → their column names, read directly via sql.js
 *  (works without spawning daas-mcp). Excludes scraw_configs. */
export async function getSourceTableColumns(): Promise<Record<string, string[]>> {
  try {
    const db = await getDb('daas');
    const tables = listTables(db).filter(
      (t) => t.startsWith('scraw_') && t !== 'scraw_configs',
    );
    const map: Record<string, string[]> = {};
    for (const t of tables) {
      try {
        map[t] = getTableColumns(db, t).map((c: any) => String(c.name));
      } catch {
        map[t] = [];
      }
    }
    return map;
  } catch {
    return {};
  }
}

/** Configured daas-mcp model names (from `list_models`). Returns
 *  `{models: [], error}` when daas-mcp is unavailable. */
export async function getModels(): Promise<{ models: string[]; error?: string }> {
  try {
    const data = await callTool('daas-mcp', 'list_models');
    const arr = Array.isArray(data) ? data : data?.models || [];
    const names = arr
      .map((m: any) => (typeof m === 'string' ? m : m?.name || m?.model))
      .filter(Boolean);
    return { models: names };
  } catch (e: any) {
    return { models: [], error: e?.message ?? String(e) };
  }
}

/** Fixed math-op catalog (from `list_indicator_ops`): `[{name, required_params, description}, ...]`.
 *  Returns `{ops: [], error}` when daas-mcp is unavailable. */
export async function getIndicatorOps(): Promise<{ ops: any[]; error?: string }> {
  try {
    const data = await callTool('daas-mcp', 'list_indicator_ops');
    const arr = Array.isArray(data) ? data : data?.ops || [];
    return { ops: arr };
  } catch (e: any) {
    return { ops: [], error: e?.message ?? String(e) };
  }
}
