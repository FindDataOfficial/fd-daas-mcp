// @ts-nocheck
import fs from 'fs';
import path from 'path';
import { REPO_ROOT } from './paths';

export const ROOT_ENV = path.join(REPO_ROOT, '.env');

/**
 * Resolve the .env file path for a settings scope.
 * 'global' (or empty) → repo-root .env; otherwise mcp/<scope>/.env.
 */
export function envPathForScope(scope: string): string {
  if (!scope || scope === 'global') return ROOT_ENV;
  return path.join(REPO_ROOT, 'mcp', scope, '.env');
}

/** Extract the env key from a `KEY=value` line, or null for comments/blanks. */
function lineKey(line: string): string | null {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#')) return null;
  const eq = trimmed.indexOf('=');
  if (eq === -1) return null;
  return trimmed.slice(0, eq);
}

/**
 * Line-patch `KEY=value` into the scope's .env file: replace the existing line
 * if the key is present, else append. Preserves comments, blank lines, and all
 * other keys. Creates the file (and its parent dir) on first write.
 */
export function syncKeyToEnv(scope: string, key: string, value: string): void {
  const filePath = envPathForScope(scope);
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  const lines = fs.existsSync(filePath)
    ? fs.readFileSync(filePath, 'utf-8').split('\n')
    : [];

  const line = `${key}=${value}`;
  let found = false;
  for (let i = 0; i < lines.length; i++) {
    if (lineKey(lines[i]) === key) {
      lines[i] = line;
      found = true;
      break;
    }
  }
  if (!found) {
    // Strip trailing empty lines so append doesn't accumulate blank lines
    // (mirrors the original `content.trimEnd() + '\n' + line` behavior).
    while (lines.length && lines[lines.length - 1] === '') lines.pop();
    lines.push(line);
  }

  let out = lines.join('\n');
  if (!out.endsWith('\n')) out += '\n';
  fs.writeFileSync(filePath, out, 'utf-8');
}

/**
 * Remove the `KEY=...` line from the scope's .env file. Preserves comments,
 * blanks, and all other keys. No-op if the file or key doesn't exist.
 */
export function removeKeyFromEnv(scope: string, key: string): void {
  const filePath = envPathForScope(scope);
  if (!fs.existsSync(filePath)) return;
  const lines = fs.readFileSync(filePath, 'utf-8').split('\n');
  const filtered = lines.filter((l) => lineKey(l) !== key);
  let out = filtered.join('\n');
  if (out && !out.endsWith('\n')) out += '\n';
  fs.writeFileSync(filePath, out, 'utf-8');
}

export function readRootEnv(): string {
  return fs.existsSync(ROOT_ENV) ? fs.readFileSync(ROOT_ENV, 'utf-8') : '';
}

export function writeRootEnv(content: string): void {
  fs.writeFileSync(ROOT_ENV, content, 'utf-8');
}
