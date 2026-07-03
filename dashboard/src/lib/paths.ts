// @ts-nocheck
// Shared repo-root locator for the dashboard.
//
// The dashboard's Next.js server code is bundled into .next/server/, so
// `__dirname` is useless for finding the source tree / `mcp/`. And
// `process.cwd()` is only `dashboard/` when the server is launched from there
// (launched from the repo root, or from an editor, it is not). So we walk up
// from `process.cwd()` until we find the directory that actually contains both
// `mcp/daas-mcp/` and `dashboard/` — that is the cli-anything repo root, and it
// is the anchor for both the sql.js read path (mcp/daas.db) and the writer
// spawn path (mcp/daas-mcp/collection_writer.py). See
// openspec/changes/fix-collection-create-error/design.md.

import fs from 'fs';
import path from 'path';

const MARKERS = ['mcp/daas-mcp/collection_writer.py', 'dashboard/package.json'];

/**
 * Walk up from `process.cwd()` until an ancestor contains every entry in
 * `MARKERS`. Returns that directory (the cli-anything repo root). Throws a
 * clear error if no ancestor matches — failing loudly is better than silently
 * resolving reads and writes to different wrong paths.
 */
export function findRepoRoot(): string {
  let dir = path.resolve(process.cwd());
  for (let i = 0; i < 24; i++) {
    if (MARKERS.every((m) => fs.existsSync(path.join(dir, m)))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break; // filesystem root
    dir = parent;
  }
  throw new Error(
    `findRepoRoot: could not locate the cli-anything repo root ` +
      `(markers ${MARKERS.join(' + ')} not found in any ancestor of ${process.cwd()}). ` +
      `Launch the dashboard from within the cli-anything repo.`,
  );
}

export const REPO_ROOT = findRepoRoot();
