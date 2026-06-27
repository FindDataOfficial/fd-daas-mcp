// @ts-nocheck
import { getDb, queryAll, saveDb } from '@/lib/db';
import fs from 'fs';
import path from 'path';
import { SettingsForm } from './settings-form';

const ROOT_ENV = path.join(process.cwd(), '..', '.env');

const MCP_SCOPES = [
  'daas-mcp', 'cron-mcp', 'leader-mcp', 'ckan-mcp',
  'cnstats-mcp', 'worldbank-mcp', 'akshare-mcp',
  'dashboard-mcp', 'scrapling-uv-mcp', 'scrapling-docker-mcp',
];

const BOOTSTRAP_KEYS = [
  { key: 'DAAS_DATABASE_URL', desc: 'Database path for all MCPs and dashboard' },
  { key: 'DASHBOARD_PORT', desc: 'Dashboard dev server port' },
];

const RUNTIME_KEYS = [
  { key: 'HTTP_PROXY', desc: 'HTTP proxy for outbound requests' },
  { key: 'HTTPS_PROXY', desc: 'HTTPS proxy for outbound requests' },
  { key: 'NO_PROXY', desc: 'Hosts that bypass the proxy' },
  { key: 'CKAN_URL', desc: 'CKAN portal API URL' },
  { key: 'LLM_BASE_URL', desc: 'OpenAI-compatible LLM API base URL' },
  { key: 'LLM_API_KEY', desc: 'API key for the LLM provider' },
  { key: 'LLM_MODEL', desc: 'Default LLM model name' },
];

function parseEnvFile(filePath: string): Record<string, string> {
  const vars: Record<string, string> = {};
  if (!fs.existsSync(filePath)) return vars;
  const content = fs.readFileSync(filePath, 'utf-8');
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq);
    const value = trimmed.slice(eq + 1);
    vars[key] = value;
  }
  return vars;
}

async function ensureSeed() {
  const db = await getDb('daas');
  const existing = queryAll(db, 'SELECT COUNT(*) as cnt FROM settings');
  if (Number(existing[0]?.cnt ?? 0) > 0) return;

  const rootVars = parseEnvFile(ROOT_ENV);

  // Seed bootstrap keys from root .env
  for (const { key, desc } of BOOTSTRAP_KEYS) {
    const val = rootVars[key];
    if (val) {
      db.run(
        "INSERT INTO settings (scope, key, value, category, description, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        ['global', key, val, 'bootstrap', desc]
      );
    }
  }

  // Seed runtime keys from root .env
  for (const { key, desc } of RUNTIME_KEYS) {
    let val = rootVars[key];
    // CKAN_PORTAL_URL maps to CKAN_URL
    if (key === 'CKAN_URL' && !val) {
      val = rootVars['CKAN_PORTAL_URL'];
    }
    if (val) {
      db.run(
        "INSERT INTO settings (scope, key, value, category, description, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        ['global', key, val, 'runtime', desc]
      );
    }
  }

  // Seed per-MCP .env overrides
  for (const mcp of MCP_SCOPES) {
    const mcpEnvPath = path.join(process.cwd(), '..', 'mcp', mcp, '.env');
    const mcpVars = parseEnvFile(mcpEnvPath);
    for (const key of ['HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY']) {
      const val = mcpVars[key];
      if (val) {
        db.run(
          "INSERT INTO settings (scope, key, value, category, description, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
          [mcp, key, val, 'runtime', `Proxy override for ${mcp}`]
        );
      }
    }
  }

  saveDb('daas');
}

export default async function SettingsPage() {
  await ensureSeed();
  const db = await getDb('daas');
  const allSettings = queryAll(db, 'SELECT * FROM settings ORDER BY category, scope, key');

  const bootstrapVars = allSettings.filter((s: any) => s.category === 'bootstrap');
  const runtimeGlobal = allSettings.filter((s: any) => s.category === 'runtime' && s.scope === 'global');
  const runtimePerMcp = allSettings.filter((s: any) => s.category === 'runtime' && s.scope !== 'global');

  // Build per-MCP lookup: { 'daas-mcp': { HTTP_PROXY: row, ... } }
  const perMcpMap: Record<string, Record<string, any>> = {};
  for (const s of runtimePerMcp) {
    if (!perMcpMap[s.scope]) perMcpMap[s.scope] = {};
    perMcpMap[s.scope][s.key] = s;
  }
  const globalRuntimeMap: Record<string, any> = {};
  for (const s of runtimeGlobal) {
    globalRuntimeMap[s.key] = s;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      {/* ── Bootstrap Section ── */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">
          Bootstrap Settings
          <span className="ml-2 text-xs font-normal text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
            Restart Required
          </span>
        </h2>
        <p className="text-sm text-gray-500 mb-3">
          These values are loaded at startup. Changes are synced to <code>.env</code> but require restarting affected services.
        </p>
        <div className="border rounded-lg bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="px-4 py-2 w-48">Key</th>
                <th className="px-4 py-2">Value</th>
                <th className="px-4 py-2 w-24">Scope</th>
                <th className="px-4 py-2 w-24">Actions</th>
              </tr>
            </thead>
            <tbody>
              {BOOTSTRAP_KEYS.map(({ key, desc }) => {
                const row = bootstrapVars.find((s: any) => s.key === key && s.scope === 'global');
                const val = row?.value || '';
                return (
                  <tr key={key} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium" title={desc}>{key}</td>
                    <td className="px-4 py-2 font-mono text-xs">{val || '(not set)'}</td>
                    <td className="px-4 py-2">
                      <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded">global</span>
                    </td>
                    <td className="px-4 py-2">
                      <SettingsForm
                        scope="global"
                        keyName={key}
                        currentValue={val}
                        category="bootstrap"
                        description={desc}
                        existingId={row?.id}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Runtime Section (global) ── */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">
          Runtime Settings
          <span className="ml-2 text-xs font-normal text-green-600 bg-green-50 px-2 py-0.5 rounded">
            Live
          </span>
        </h2>
        <p className="text-sm text-gray-500 mb-3">
          Changes take effect immediately on the next MCP tool invocation. No restart needed.
        </p>
        <div className="border rounded-lg bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="px-4 py-2 w-48">Key</th>
                <th className="px-4 py-2">Value</th>
                <th className="px-4 py-2 w-24">Scope</th>
                <th className="px-4 py-2 w-24">Actions</th>
              </tr>
            </thead>
            <tbody>
              {RUNTIME_KEYS.map(({ key, desc }) => {
                const row = globalRuntimeMap[key];
                const val = row?.value || '';
                return (
                  <tr key={key} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium" title={desc}>{key}</td>
                    <td className="px-4 py-2 font-mono text-xs">{val || '(not set)'}</td>
                    <td className="px-4 py-2">
                      <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded">global</span>
                    </td>
                    <td className="px-4 py-2">
                      <SettingsForm
                        scope="global"
                        keyName={key}
                        currentValue={val}
                        category="runtime"
                        description={desc}
                        existingId={row?.id}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Per-MCP Proxy Overrides ── */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Per-MCP Proxy Overrides</h2>
        <p className="text-sm text-gray-500 mb-3">
          Each MCP can override the global proxy settings. &quot;(inherited)&quot; means the global value is used.
        </p>
        <div className="border rounded-lg bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="px-4 py-2 w-40">MCP</th>
                <th className="px-4 py-2">HTTP_PROXY</th>
                <th className="px-4 py-2">HTTPS_PROXY</th>
                <th className="px-4 py-2 w-24">Actions</th>
              </tr>
            </thead>
            <tbody>
              {MCP_SCOPES.map((mcp) => {
                const httpRow = perMcpMap[mcp]?.['HTTP_PROXY'];
                const httpsRow = perMcpMap[mcp]?.['HTTPS_PROXY'];
                const globalHttp = globalRuntimeMap['HTTP_PROXY']?.value || '';
                const globalHttps = globalRuntimeMap['HTTPS_PROXY']?.value || '';

                const httpVal = httpRow?.value || '';
                const httpsVal = httpsRow?.value || '';
                const httpCustom = !!httpRow;
                const httpsCustom = !!httpsRow;

                return (
                  <tr key={mcp} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium">{mcp}</td>
                    <td className="px-4 py-2">
                      {httpCustom ? (
                        <span className="font-mono text-xs">{httpVal}</span>
                      ) : (
                        <span className="text-gray-400 italic text-xs">
                          (inherited) {globalHttp || '(not set)'}
                        </span>
                      )}
                      {httpCustom && (
                        <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">Custom</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      {httpsCustom ? (
                        <span className="font-mono text-xs">{httpsVal}</span>
                      ) : (
                        <span className="text-gray-400 italic text-xs">
                          (inherited) {globalHttps || '(not set)'}
                        </span>
                      )}
                      {httpsCustom && (
                        <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">Custom</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex gap-1">
                        <SettingsForm
                          scope={mcp}
                          keyName="HTTP_PROXY"
                          currentValue={httpVal}
                          category="runtime"
                          description={`HTTP proxy override for ${mcp}`}
                          existingId={httpRow?.id}
                          buttonLabel="HTTP"
                        />
                        <SettingsForm
                          scope={mcp}
                          keyName="HTTPS_PROXY"
                          currentValue={httpsVal}
                          category="runtime"
                          description={`HTTPS proxy override for ${mcp}`}
                          existingId={httpsRow?.id}
                          buttonLabel="HTTPS"
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
