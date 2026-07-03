// Spawn a Python sidecar CLI under mcp/daas-mcp and parse its stdout as JSON.
// Used by the collections write routes; could be reused for other mutating
// dashboard → MCP-source operations.

import { spawn } from 'child_process';
import path from 'path';
import { REPO_ROOT } from './paths';

const DAAS_MCP_DIR = path.join(REPO_ROOT, 'mcp', 'daas-mcp');

export interface RunResult<T = any> {
  ok: boolean;
  data?: T;
  error?: string;
  exitCode: number;
}

/**
 * Run `uv run --directory <daas-mcp dir> python <cli> <command> --json <json>`
 * and return the parsed stdout JSON. On failure (non-zero exit, error JSON in
 * stdout, or non-JSON output), returns `{ ok: false, error, exitCode }`.
 *
 * ponytail: one subprocess per write. Slow under load, fine for the dashboard.
 */
export function runPythonCli<T = any>(
  cli: string,
  command: string | null,
  args: object,
  opts: { timeoutMs?: number; env?: NodeJS.ProcessEnv } = {},
): Promise<RunResult<T>> {
  return new Promise((resolve) => {
    const jsonArg = JSON.stringify(args);
    const argv = ['run', '--directory', DAAS_MCP_DIR, 'python', cli];
    if (command) argv.push(command);
    argv.push('--json', jsonArg);

    const child = spawn('uv', argv, {
      cwd: DAAS_MCP_DIR,
      env: { ...process.env, ...(opts.env ?? {}) },
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (b) => { stdout += b.toString(); });
    child.stderr.on('data', (b) => { stderr += b.toString(); });

    const timeout = setTimeout(() => {
      child.kill('SIGKILL');
    }, opts.timeoutMs ?? 60_000);

    child.on('close', (code) => {
      clearTimeout(timeout);
      const exit = code ?? 1;

      // Prefer the last non-empty stdout line that parses as JSON. The CLI
      // mirrors errors to both stdout and stderr; we accept either.
      const lines = stdout.split('\n').filter((l) => l.trim().length > 0);
      const lastLine = lines[lines.length - 1];
      let parsed: any = null;
      if (lastLine) {
        try { parsed = JSON.parse(lastLine); } catch { /* fallthrough */ }
      }
      if (parsed && typeof parsed === 'object' && 'error' in parsed) {
        resolve({ ok: false, error: String(parsed.error), exitCode: exit });
        return;
      }
      if (exit !== 0) {
        resolve({
          ok: false,
          error: stderr.trim() || `python exited with ${exit}`,
          exitCode: exit,
        });
        return;
      }
      if (parsed === null) {
        resolve({
          ok: false,
          error: `non-JSON stdout: ${stdout.slice(0, 200)}`,
          exitCode: exit,
        });
        return;
      }
      resolve({ ok: true, data: parsed as T, exitCode: exit });
    });

    child.on('error', (err) => {
      clearTimeout(timeout);
      resolve({ ok: false, error: err.message, exitCode: -1 });
    });
  });
}
