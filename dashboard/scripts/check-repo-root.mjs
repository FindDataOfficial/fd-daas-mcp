// Node-side mirror of dashboard/src/lib/paths.ts findRepoRoot(), used by the
// Python self-check (mcp/daas-mcp/selfcheck_collection_writer.py) to assert
// the TS walk-up and the Python `__file__`-based `parents[2]` anchor resolve
// to the same repo root, even when run from a non-`dashboard/` cwd (the
// regression case: the dashboard launched from the repo root).
//
// MARKERS must stay in sync with dashboard/src/lib/paths.ts. Kept as plain
// .mjs (no TS toolchain) so it runs under bare `node` — the goal is to test
// the walk logic + markers, not to import the bundled paths.ts module.
//
// Usage:
//   node check-repo-root.mjs                  # prints the resolved repo root
//   node check-repo-root.mjs --expected <path> # exits 0 iff it matches
import fs from 'fs';
import path from 'path';

const MARKERS = ['mcp/daas-mcp/collection_writer.py', 'dashboard/package.json'];

function findRepoRoot() {
  let dir = path.resolve(process.cwd());
  for (let i = 0; i < 24; i++) {
    if (MARKERS.every((m) => fs.existsSync(path.join(dir, m)))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error(
    `findRepoRoot: could not locate repo root (markers ${MARKERS.join(' + ')} not found in any ancestor of ${process.cwd()})`,
  );
}

const root = findRepoRoot();
const expected = process.argv.includes('--expected')
  ? process.argv[process.argv.indexOf('--expected') + 1]
  : null;

if (expected !== null && expected !== undefined) {
  if (path.resolve(expected) !== root) {
    console.error(`mismatch: expected ${expected}, got ${root}`);
    process.exit(1);
  }
}
console.log(root);
