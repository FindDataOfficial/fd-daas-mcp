#!/usr/bin/env node
// One-command headless e2e runner for the dashboard.
//
// Starts `next dev` on the Cypress baseUrl port, waits for it to be ready,
// then runs each Cypress spec file in its OWN `cypress run` process. Running
// one spec per process sidesteps a between-specs browser-relaunch hang that
// occurs on some machines (Node 25 + Chrome) where Chrome fails to reconnect
// for the second spec. A fresh process launches its browser once and exits.
//
// Usage:
//   node scripts/run-e2e.mjs                 # start server + run all specs
//   E2E_BROWSER=electron node scripts/run-e2e.mjs   # override browser
//   E2E_PORT=3459 node scripts/run-e2e.mjs           # override port
//
// Exits non-zero if any spec fails. Tears the server down on exit.
import { spawn, spawnSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DASH = resolve(HERE, '..');

const PORT = process.env.E2E_PORT || '3459';
const BASE_URL = `http://localhost:${PORT}`;
const BROWSER = process.env.E2E_BROWSER || 'chrome';
const SPECS_DIR = resolve(DASH, 'cypress/e2e');

function log(msg) {
  process.stdout.write(`${msg}\n`);
}

async function waitForServer(url, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, { method: 'HEAD' });
      // 200 or 3xx (Next redirects / to /databases) both mean the server is up.
      if (res.status < 500) return true;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

async function main() {
  // 1. Collect spec files.
  const specs = readdirSync(SPECS_DIR)
    .filter((f) => f.endsWith('.cy.ts'))
    .sort();
  if (specs.length === 0) {
    log('No spec files found in cypress/e2e/');
    process.exit(1);
  }
  log(`Found ${specs.length} spec file(s): ${specs.join(', ')}`);

  // 2. Start next dev (or reuse an already-running server on the port).
  let serverProc = null;
  let startedOurs = false;
  const alreadyUp = await waitForServer(BASE_URL, 3000);
  if (alreadyUp) {
    log(`Server already running at ${BASE_URL} — reusing it.`);
  } else {
    log(`Starting next dev on port ${PORT} ...`);
    serverProc = spawn(
      'npx',
      ['next', 'dev', `--port=${PORT}`],
      { cwd: DASH, stdio: 'ignore', detached: false },
    );
    startedOurs = true;
    serverProc.on('error', (err) => {
      log(`Failed to start next dev: ${err.message}`);
      process.exit(1);
    });
    log(`Waiting for ${BASE_URL} to be ready (up to 120s) ...`);
    const ok = await waitForServer(BASE_URL, 120000);
    if (!ok) {
      log(`Server did not become ready at ${BASE_URL} within 120s.`);
      if (serverProc) serverProc.kill('SIGKILL');
      process.exit(1);
    }
    log('Server ready.');
  }

  // 3. Run each spec in its own cypress process.
  const results = [];
  const cypressBin = resolve(DASH, 'node_modules/.bin/cypress');
  for (const spec of specs) {
    const specPath = `cypress/e2e/${spec}`;
    log(`\n▶ Running ${spec} (${BROWSER}) ...`);
    const res = spawnSync(
      cypressBin,
      ['run', '--browser', BROWSER, '--spec', specPath],
      { cwd: DASH, stdio: 'inherit' },
    );
    const passed = res.status === 0;
    results.push({ spec, passed, exitCode: res.status });
    log(`${passed ? '✓ PASS' : '✗ FAIL'} — ${spec}`);
  }

  // 4. Teardown.
  if (startedOurs && serverProc) {
    log('\nTearing down next dev ...');
    try {
      serverProc.kill('SIGTERM');
      setTimeout(() => serverProc.kill('SIGKILL'), 3000);
    } catch {
      // best-effort
    }
  }

  // 5. Summary.
  log('\n========================================================');
  log('e2e summary:');
  for (const r of results) {
    log(`  ${r.passed ? '✓' : '✗'} ${r.spec}`);
  }
  const failed = results.filter((r) => !r.passed);
  log(`\n${results.length - failed.length}/${results.length} spec(s) passed.`);
  process.exit(failed.length === 0 ? 0 : 1);
}

main().catch((err) => {
  log(`Runner error: ${err.stack || err.message}`);
  process.exit(1);
});
