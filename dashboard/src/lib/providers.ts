import { anthropic } from '@ai-sdk/anthropic';
import { openai, createOpenAI } from '@ai-sdk/openai';
import { google } from '@ai-sdk/google';

export type ProviderName = 'anthropic' | 'openai' | 'google' | 'openrouter' | 'ollama' | 'volcengine';

export interface RawProviderConfig {
  _raw: true;
  provider: string;
  model: string;
  apiKey: string;
  baseURL: string;
}

const PROVIDER_API_KEYS: Record<ProviderName, string> = {
  anthropic: 'ANTHROPIC_API_KEY',
  openai: 'OPENAI_API_KEY',
  google: 'GOOGLE_GENERATIVE_AI_API_KEY',
  openrouter: 'OPENROUTER_API_KEY',
  ollama: 'none',
  volcengine: 'VOLCENGINE_API_KEY',
};

const PROVIDER_BASE_URLS: Partial<Record<ProviderName, string>> = {
  volcengine: 'https://ark.cn-beijing.volces.com/api/coding/v3',
};

const DEFAULT_MODELS: Record<ProviderName, string> = {
  anthropic: 'claude-sonnet-4-6',
  openai: 'gpt-4o',
  google: 'gemini-2.5-flash',
  openrouter: 'anthropic/claude-sonnet-4',
  ollama: 'llama3',
  volcengine: 'deepseek-v4-pro-260425',
};

export class MissingApiKeyError extends Error {
  constructor(provider: ProviderName) {
    const envVar = PROVIDER_API_KEYS[provider];
    super(`Missing API key for ${provider}. Set ${envVar} in dashboard/.env.local`);
    this.name = 'MissingApiKeyError';
  }
}

function getProvider(): ProviderName {
  return (process.env.AI_PROVIDER as ProviderName) || 'anthropic';
}

function getModelId(): string {
  const provider = getProvider();
  return process.env.AI_MODEL || DEFAULT_MODELS[provider];
}

function getApiKey(provider: ProviderName): string {
  if (provider === 'ollama') return '';
  const envVar = PROVIDER_API_KEYS[provider];
  const key = process.env[envVar];
  if (!key) throw new MissingApiKeyError(provider);
  return key;
}

/**
 * Returns an AI SDK model for anthropic/openai/google.
 * Returns RawProviderConfig for volcengine/openrouter/ollama (use raw fetch).
 */
export function getModel() {
  const provider = getProvider();
  const modelId = getModelId();

  // Providers that need raw fetch (no AI SDK compatibility issues)
  if (provider === 'volcengine' || provider === 'openrouter' || provider === 'ollama') {
    const config: RawProviderConfig = {
      _raw: true,
      provider,
      model: modelId,
      apiKey: getApiKey(provider),
      baseURL: PROVIDER_BASE_URLS[provider] || '',
    };
    if (provider === 'ollama') {
      config.baseURL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434/v1';
    } else if (provider === 'openrouter') {
      config.baseURL = 'https://openrouter.ai/api/v1';
    }
    return config;
  }

  // AI SDK native providers
  switch (provider) {
    case 'anthropic':
      return anthropic(modelId);
    case 'openai':
      return openai(modelId);
    case 'google':
      return google(modelId);
    default:
      return anthropic(modelId);
  }
}

export function getProviderInfo() {
  const provider = getProvider();
  return {
    provider,
    model: getModelId(),
    apiKeyVar: PROVIDER_API_KEYS[provider],
  };
}
