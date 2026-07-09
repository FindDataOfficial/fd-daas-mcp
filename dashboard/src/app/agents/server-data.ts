// @ts-nocheck
import { callTool } from '@/lib/mcp-call';

/**
 * Agent-form dropdown options, populated from leader-mcp:
 *   - `upstreams` from `list_data_mcps()` (enabled data-fetch MCPs)
 *   - `models` + `tiers` from `list_agent_models()` (LEADER_MODELS entries +
 *     the high/balance/fast tier mapping)
 *
 * Returns `{upstreams: [], models: [], tiers: {}, error}` when leader-mcp is
 * unavailable, so the form can fall back to free-text inputs (mirrors the
 * process rule-form's `mcpError` fallback).
 */
export interface AgentModel {
  name: string;
  model: string;
  provider?: string | null;
  vision?: boolean;
}

export interface AgentOptions {
  upstreams: string[];
  models: AgentModel[];
  tiers: Record<string, any>;
  error?: string;
}

export async function getAgentOptions(): Promise<AgentOptions> {
  const empty: AgentOptions = { upstreams: [], models: [], tiers: {} };
  try {
    const [mcps, agentModels] = await Promise.all([
      callTool('leader-mcp', 'list_data_mcps'),
      callTool('leader-mcp', 'list_agent_models'),
    ]);
    const upstreams = (mcps?.upstreams || [])
      .map((u: any) => u?.name)
      .filter(Boolean)
      .sort();
    const models = Array.isArray(agentModels?.models) ? agentModels.models : [];
    const tiers = agentModels?.tiers || {};
    return { upstreams, models, tiers };
  } catch (e: any) {
    return { ...empty, error: e?.message ?? String(e) };
  }
}
