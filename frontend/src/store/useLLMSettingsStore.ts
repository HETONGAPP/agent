/**
 * LLM Settings Store
 * User override for AI/LLM API: provider selection and API config.
 * Used when generating diagnostics (sent as llm_override in request body).
 */

import { create } from 'zustand';
import { setStorageItem, getStorageItem } from '@/utils/storage';
import { STORAGE_KEYS } from '@/config/constants';

export const LLM_PROVIDERS = [
  { value: 'ollama', label: 'Ollama' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'groq', label: 'Groq' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google' },
] as const;

export type LLMProviderValue = (typeof LLM_PROVIDERS)[number]['value'];

export interface LLMSettings {
  provider: LLMProviderValue;
  api_key: string;
  model: string;
  ollama_url: string;
  /** For OpenAI-compatible endpoints (e.g. cursor-api). Used when provider is openai. */
  base_url: string;
}

const defaults: LLMSettings = {
  provider: 'ollama',
  api_key: '',
  model: 'qwen2.5:7b',
  ollama_url: 'http://localhost:11434',
  base_url: '',
};

const getInitial = (): LLMSettings => {
  try {
    const stored = getStorageItem<Partial<LLMSettings>>(STORAGE_KEYS.LLM_SETTINGS, {});
    return {
      provider: (stored.provider as LLMProviderValue) ?? defaults.provider,
      api_key: stored.api_key ?? defaults.api_key,
      model: stored.model ?? defaults.model,
      ollama_url: stored.ollama_url ?? defaults.ollama_url,
      base_url: stored.base_url ?? defaults.base_url,
    };
  } catch {
    return { ...defaults };
  }
};

/** True when stored settings are effectively "use server default" (default Ollama, nothing custom). */
function isServerDefault(state: LLMSettings): boolean {
  if (state.provider !== 'ollama') return false;
  if (state.api_key?.trim()) return false;
  if (state.base_url?.trim()) return false;
  const modelOk = !state.model?.trim() || state.model === defaults.model;
  const urlOk = !state.ollama_url?.trim() || state.ollama_url === defaults.ollama_url;
  return modelOk && urlOk;
}

interface LLMSettingsState extends LLMSettings {
  setProvider: (p: LLMProviderValue) => void;
  setApiKey: (v: string) => void;
  setModel: (v: string) => void;
  setOllamaUrl: (v: string) => void;
  setBaseUrl: (v: string) => void;
  setSettings: (s: Partial<LLMSettings>) => void;
  getOverride: () => Partial<LLMSettings> | null;
}

export const useLLMSettingsStore = create<LLMSettingsState>((set, get) => ({
  ...getInitial(),

  setProvider: (provider) => {
    set({ provider });
    setStorageItem(STORAGE_KEYS.LLM_SETTINGS, { ...get(), provider });
  },

  setApiKey: (api_key) => {
    set({ api_key });
    setStorageItem(STORAGE_KEYS.LLM_SETTINGS, { ...get(), api_key });
  },

  setModel: (model) => {
    set({ model });
    setStorageItem(STORAGE_KEYS.LLM_SETTINGS, { ...get(), model });
  },

  setOllamaUrl: (ollama_url) => {
    set({ ollama_url });
    setStorageItem(STORAGE_KEYS.LLM_SETTINGS, { ...get(), ollama_url });
  },

  setBaseUrl: (base_url) => {
    set({ base_url });
    setStorageItem(STORAGE_KEYS.LLM_SETTINGS, { ...get(), base_url });
  },

  setSettings: (s) => {
    const next = { ...get(), ...s };
    set(next);
    setStorageItem(STORAGE_KEYS.LLM_SETTINGS, next);
  },

  getOverride: () => {
    const state = get();
    if (isServerDefault(state)) return null;
    return {
      provider: state.provider,
      ...(state.api_key?.trim() && { api_key: state.api_key.trim() }),
      ...(state.model?.trim() && { model: state.model.trim() }),
      ...(state.provider === 'ollama' && state.ollama_url?.trim() && { ollama_url: state.ollama_url.trim() }),
      ...(state.provider === 'openai' && state.base_url?.trim() && { base_url: state.base_url.trim() }),
    };
  },
}));
