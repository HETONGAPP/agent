/**
 * Settings Page
 * Layout: App settings (application behavior) and User settings (personal preferences).
 * Changes take effect only after clicking Save.
 */

import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Map, Clock, List, Cpu, User, Bot, Eye, EyeOff, Save, Server } from 'lucide-react';
import { useMapThemeStore, type MapTheme } from '@/store/useMapThemeStore';
import { useTimezoneStore, TIMEZONE_OPTIONS } from '@/store/useTimezoneStore';
import { usePreferencesStore, type TimeFormatPreference } from '@/store/usePreferencesStore';
import { useLLMSettingsStore, LLM_PROVIDERS, type LLMProviderValue } from '@/store/useLLMSettingsStore';
import { PAGINATION } from '@/config/constants';
import { useToastStore } from '@/store/useToastStore';
import {
  getInfrastructureSettings,
  putInfrastructureSettings,
  type InfrastructureServer,
} from '@/api/settings';

const MASKED_PLACEHOLDER = '***';
function defaultInfra(): InfrastructureServer {
  return {
    redis: { host: '', port: 6379, db: 0, password: '' },
    influxdb: { url: '', org: '', bucket: '', token: '' },
    postgresql: { host: '', port: 5432, database: '', user: '', password: '' },
    mqtt: { broker_url: '', client_id: '', username: '', password: '' },
  };
}

const cardClass = 'rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-6 sm:shadow-lg';
const cardTitleClass = 'flex items-center gap-3 text-gray-400 mb-4';
const cardDescClass = 'text-gray-500 text-sm mb-4';
const inputClass = 'w-full max-w-md rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500';

function getInitialForm() {
  const map = useMapThemeStore.getState();
  const tz = useTimezoneStore.getState();
  const prefs = usePreferencesStore.getState();
  const llm = useLLMSettingsStore.getState();
  return {
    mapTheme: map.mapTheme,
    timezone: tz.timezone,
    defaultPageSize: prefs.defaultPageSize,
    timeFormat: prefs.timeFormat,
    llmProvider: llm.provider,
    llmApiKey: llm.api_key,
    llmModel: llm.model,
    llmOllamaUrl: llm.ollama_url,
    llmBaseUrl: llm.base_url ?? '',
    infra: defaultInfra(),
  };
}

type InfraPasswordKey = 'redis' | 'influxdb' | 'postgresql' | 'mqtt';

export const Settings = () => {
  const [form, setForm] = useState(getInitialForm);
  const [showApiKey, setShowApiKey] = useState(false);
  const [originalInfra, setOriginalInfra] = useState<InfrastructureServer | null>(null);
  const [infraLoading, setInfraLoading] = useState(true);
  const [infraLoadError, setInfraLoadError] = useState(false);
  const [showPasswords, setShowPasswords] = useState<Record<InfraPasswordKey, boolean>>({
    redis: false,
    influxdb: false,
    postgresql: false,
    mqtt: false,
  });
  const addToast = useToastStore((s) => s.addToast);

  useEffect(() => {
    setForm(getInitialForm());
  }, []);

  useEffect(() => {
    setInfraLoading(true);
    setInfraLoadError(false);
    getInfrastructureSettings()
      .then((res) => {
        setForm((prev) => ({ ...prev, infra: res.data }));
        setOriginalInfra(res.data);
      })
      .catch(() => {
        setInfraLoadError(true);
        addToast('Failed to load infrastructure settings', 'error');
      })
      .finally(() => setInfraLoading(false));
  }, [addToast]);

  const toggleShowPassword = (key: InfraPasswordKey) => {
    setShowPasswords((p) => ({ ...p, [key]: !p[key] }));
  };

  const handleSave = async () => {
    useMapThemeStore.getState().setMapTheme(form.mapTheme as MapTheme);
    useTimezoneStore.getState().setTimezone(form.timezone);
    usePreferencesStore.getState().setDefaultPageSize(form.defaultPageSize);
    usePreferencesStore.getState().setTimeFormat(form.timeFormat as TimeFormatPreference);
    useLLMSettingsStore.getState().setSettings({
      provider: form.llmProvider as LLMProviderValue,
      api_key: form.llmApiKey,
      model: form.llmModel,
      ollama_url: form.llmOllamaUrl,
      base_url: form.llmBaseUrl ?? '',
    });

    const infra = form.infra;
    const orig = originalInfra;
    const mask = (val: string, origVal: string | undefined) =>
      val === MASKED_PLACEHOLDER || (origVal !== undefined && val === origVal) ? '__MASKED__' : val;

    try {
      await putInfrastructureSettings({
        database: {
          redis: {
            host: infra.redis.host,
            port: infra.redis.port,
            db: infra.redis.db,
            password: mask(infra.redis.password, orig?.redis.password),
          },
          influxdb: {
            url: infra.influxdb.url,
            org: infra.influxdb.org,
            bucket: infra.influxdb.bucket,
            token: mask(infra.influxdb.token, orig?.influxdb.token),
          },
          postgresql: {
            host: infra.postgresql.host,
            port: infra.postgresql.port,
            database: infra.postgresql.database,
            user: infra.postgresql.user,
            password: mask(infra.postgresql.password, orig?.postgresql.password),
          },
        },
        mqtt: {
          broker_url: infra.mqtt.broker_url,
          client_id: infra.mqtt.client_id,
          username: infra.mqtt.username,
          password: mask(infra.mqtt.password, orig?.mqtt.password),
        },
      });
      setOriginalInfra(infra);
      addToast('Settings saved. Restart agent to apply infrastructure changes.', 'success');
    } catch {
      addToast('Other settings saved. Failed to save infrastructure (check network).', 'error');
    }
  };

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="px-4 py-6 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white mb-1">Settings</h1>
            <p className="text-gray-400 text-sm">Application and user preferences. Changes take effect after Save.</p>
          </div>
          <button
            type="button"
            onClick={handleSave}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm shadow-lg focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-gray-900 transition-colors"
          >
            <Save size={18} />
            Save
          </button>
        </div>

        {/* App settings */}
        <section className="mb-10">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-white mb-4 pb-2 border-b border-white/10">
            <Cpu className="text-blue-400" size={20} />
            App settings
          </h2>
          <p className="text-gray-500 text-sm mb-4">Application appearance and default behavior.</p>
          <div className="space-y-6">
            <div className={cardClass}>
              <div className={cardTitleClass}>
                <Map className="text-blue-400" size={20} />
                <h3 className="text-base font-semibold text-white">Map color</h3>
              </div>
              <p className={cardDescClass}>Map tile style on Data Center page.</p>
              <div className="flex gap-3">
                {(['dark', 'light'] as const).map((theme) => (
                  <button
                    key={theme}
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, mapTheme: theme }))}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${
                      form.mapTheme === theme
                        ? 'bg-blue-600 text-white ring-2 ring-blue-400'
                        : 'bg-white/10 text-gray-300 hover:bg-white/15 hover:text-white'
                    }`}
                  >
                    {theme}
                  </button>
                ))}
              </div>
            </div>

            <div className={cardClass}>
              <div className={cardTitleClass}>
                <Bot className="text-blue-400" size={20} />
                <h3 className="text-base font-semibold text-white">LLM / AI model</h3>
              </div>
              <p className={cardDescClass}>API provider and config for diagnostic generation. Override is sent with generate requests.</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-gray-400 text-sm mb-1">Provider</label>
                  <select
                    value={form.llmProvider}
                    onChange={(e) => setForm((f) => ({ ...f, llmProvider: e.target.value as LLMProviderValue }))}
                    className={inputClass}
                  >
                    {LLM_PROVIDERS.map((opt) => (
                      <option key={opt.value} value={opt.value} className="bg-gray-800 text-white">
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-400 text-sm mb-1">API key (optional for Ollama)</label>
                  <div className="relative max-w-md">
                    <input
                      type={showApiKey ? 'text' : 'password'}
                      value={form.llmApiKey}
                      onChange={(e) => setForm((f) => ({ ...f, llmApiKey: e.target.value }))}
                      placeholder="Leave empty to use server default"
                      className={`${inputClass} pr-10`}
                      autoComplete="off"
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey((v) => !v)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-gray-400 hover:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                      aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
                    >
                      {showApiKey ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-gray-400 text-sm mb-1">Model</label>
                  <input
                    type="text"
                    value={form.llmModel}
                    onChange={(e) => setForm((f) => ({ ...f, llmModel: e.target.value }))}
                    placeholder={form.llmProvider === 'ollama' ? 'e.g. qwen2.5:7b' : 'e.g. gpt-4'}
                    className={inputClass}
                  />
                </div>
                {form.llmProvider === 'ollama' && (
                  <div>
                    <label className="block text-gray-400 text-sm mb-1">Ollama URL</label>
                    <input
                      type="url"
                      value={form.llmOllamaUrl}
                      onChange={(e) => setForm((f) => ({ ...f, llmOllamaUrl: e.target.value }))}
                      placeholder="http://localhost:11434"
                      className={inputClass}
                    />
                  </div>
                )}
                {form.llmProvider === 'openai' && (
                  <div>
                    <label className="block text-gray-400 text-sm mb-1">Base URL (e.g. cursor-api)</label>
                    <input
                      type="url"
                      value={form.llmBaseUrl ?? ''}
                      onChange={(e) => setForm((f) => ({ ...f, llmBaseUrl: e.target.value }))}
                      placeholder="http://localhost:3001"
                      className={inputClass}
                    />
                  </div>
                )}
              </div>
            </div>

            <div className={cardClass}>
              <div className={cardTitleClass}>
                <List className="text-blue-400" size={20} />
                <h3 className="text-base font-semibold text-white">Default page size</h3>
              </div>
              <p className={cardDescClass}>Number of items per page in lists (e.g. Devices).</p>
              <select
                value={form.defaultPageSize}
                onChange={(e) => setForm((f) => ({ ...f, defaultPageSize: Number(e.target.value) }))}
                className="w-full max-w-xs rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {PAGINATION.PAGE_SIZE_OPTIONS.map((n) => (
                  <option key={n} value={n} className="bg-gray-800 text-white">
                    {n}
                  </option>
                ))}
              </select>
            </div>

            {/* Infrastructure */}
            <div className={cardClass}>
              <div className={cardTitleClass}>
                <Server className="text-blue-400" size={20} />
                <h3 className="text-base font-semibold text-white">Infrastructure</h3>
              </div>
              <p className={cardDescClass}>
                Redis, InfluxDB, MQTT, PostgreSQL. Values are loaded from the server when you open this page. If fields are empty, the server may have no config or the request failed—fill in manually and click Save to write overrides. Restart the agent to apply.
              </p>
              {infraLoading && (
                <p className="text-sm text-amber-400/90 mb-4">Loading infrastructure from server…</p>
              )}
              {!infraLoading && infraLoadError && (
                <p className="text-sm text-amber-400/90 mb-4">Could not load from server. You can fill in the fields below and Save to write overrides.</p>
              )}
              <div className="space-y-6">
                <div>
                  <h4 className="text-sm font-medium text-gray-300 mb-3">Redis</h4>
                  <div className="grid gap-3 sm:grid-cols-2 max-w-2xl">
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Host</label>
                      <input
                        type="text"
                        value={form.infra.redis.host}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, redis: { ...f.infra.redis, host: e.target.value } } }))}
                        placeholder="localhost"
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Port</label>
                      <input
                        type="number"
                        value={form.infra.redis.port}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, redis: { ...f.infra.redis, port: Number(e.target.value) || 0 } } }))}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">DB</label>
                      <input
                        type="number"
                        value={form.infra.redis.db}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, redis: { ...f.infra.redis, db: Number(e.target.value) || 0 } } }))}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Password</label>
                      <div className="relative max-w-md">
                        <input
                          type={showPasswords.redis ? 'text' : 'password'}
                          value={form.infra.redis.password}
                          onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, redis: { ...f.infra.redis, password: e.target.value } } }))}
                          placeholder="Leave empty or unchanged to keep existing"
                          className={`${inputClass} pr-10`}
                          autoComplete="off"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShowPassword('redis')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-gray-400 hover:text-white"
                          aria-label={showPasswords.redis ? 'Hide password' : 'Show password'}
                        >
                          {showPasswords.redis ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-300 mb-3">InfluxDB</h4>
                  <div className="grid gap-3 sm:grid-cols-2 max-w-2xl">
                    <div className="sm:col-span-2">
                      <label className="block text-gray-400 text-sm mb-1">URL</label>
                      <input
                        type="url"
                        value={form.infra.influxdb.url}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, influxdb: { ...f.infra.influxdb, url: e.target.value } } }))}
                        placeholder="http://localhost:8086"
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Org</label>
                      <input
                        type="text"
                        value={form.infra.influxdb.org}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, influxdb: { ...f.infra.influxdb, org: e.target.value } } }))}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Bucket</label>
                      <input
                        type="text"
                        value={form.infra.influxdb.bucket}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, influxdb: { ...f.infra.influxdb, bucket: e.target.value } } }))}
                        className={inputClass}
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-gray-400 text-sm mb-1">Token</label>
                      <div className="relative max-w-md">
                        <input
                          type={showPasswords.influxdb ? 'text' : 'password'}
                          value={form.infra.influxdb.token}
                          onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, influxdb: { ...f.infra.influxdb, token: e.target.value } } }))}
                          placeholder="Leave unchanged to keep existing"
                          className={`${inputClass} pr-10`}
                          autoComplete="off"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShowPassword('influxdb')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-gray-400 hover:text-white"
                          aria-label={showPasswords.influxdb ? 'Hide token' : 'Show token'}
                        >
                          {showPasswords.influxdb ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-300 mb-3">PostgreSQL</h4>
                  <div className="grid gap-3 sm:grid-cols-2 max-w-2xl">
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Host</label>
                      <input
                        type="text"
                        value={form.infra.postgresql.host}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, postgresql: { ...f.infra.postgresql, host: e.target.value } } }))}
                        placeholder="localhost"
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Port</label>
                      <input
                        type="number"
                        value={form.infra.postgresql.port}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, postgresql: { ...f.infra.postgresql, port: Number(e.target.value) || 0 } } }))}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Database</label>
                      <input
                        type="text"
                        value={form.infra.postgresql.database}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, postgresql: { ...f.infra.postgresql, database: e.target.value } } }))}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">User</label>
                      <input
                        type="text"
                        value={form.infra.postgresql.user}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, postgresql: { ...f.infra.postgresql, user: e.target.value } } }))}
                        className={inputClass}
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-gray-400 text-sm mb-1">Password</label>
                      <div className="relative max-w-md">
                        <input
                          type={showPasswords.postgresql ? 'text' : 'password'}
                          value={form.infra.postgresql.password}
                          onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, postgresql: { ...f.infra.postgresql, password: e.target.value } } }))}
                          placeholder="Leave unchanged to keep existing"
                          className={`${inputClass} pr-10`}
                          autoComplete="off"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShowPassword('postgresql')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-gray-400 hover:text-white"
                          aria-label={showPasswords.postgresql ? 'Hide password' : 'Show password'}
                        >
                          {showPasswords.postgresql ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-300 mb-3">MQTT</h4>
                  <div className="grid gap-3 sm:grid-cols-2 max-w-2xl">
                    <div className="sm:col-span-2">
                      <label className="block text-gray-400 text-sm mb-1">Broker URL</label>
                      <input
                        type="text"
                        value={form.infra.mqtt.broker_url}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, mqtt: { ...f.infra.mqtt, broker_url: e.target.value } } }))}
                        placeholder="mqtt://localhost:1883"
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Client ID</label>
                      <input
                        type="text"
                        value={form.infra.mqtt.client_id}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, mqtt: { ...f.infra.mqtt, client_id: e.target.value } } }))}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Username</label>
                      <input
                        type="text"
                        value={form.infra.mqtt.username}
                        onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, mqtt: { ...f.infra.mqtt, username: e.target.value } } }))}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-gray-400 text-sm mb-1">Password</label>
                      <div className="relative max-w-md">
                        <input
                          type={showPasswords.mqtt ? 'text' : 'password'}
                          value={form.infra.mqtt.password}
                          onChange={(e) => setForm((f) => ({ ...f, infra: { ...f.infra, mqtt: { ...f.infra.mqtt, password: e.target.value } } }))}
                          placeholder="Leave unchanged to keep existing"
                          className={`${inputClass} pr-10`}
                          autoComplete="off"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShowPassword('mqtt')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-gray-400 hover:text-white"
                          aria-label={showPasswords.mqtt ? 'Hide password' : 'Show password'}
                        >
                          {showPasswords.mqtt ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* User settings */}
        <section>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-white mb-4 pb-2 border-b border-white/10">
            <User className="text-blue-400" size={20} />
            User settings
          </h2>
          <p className="text-gray-500 text-sm mb-4">Personal preferences for display and behavior.</p>
          <div className="space-y-6">
            <div className={cardClass}>
              <div className={cardTitleClass}>
                <Clock className="text-blue-400" size={20} />
                <h3 className="text-base font-semibold text-white">Timezone / Time</h3>
              </div>
              <p className={cardDescClass}>Timezone and time format for date/time display.</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-gray-400 text-sm mb-1">Timezone</label>
                  <select
                    value={form.timezone}
                    onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
                    className="w-full max-w-xs rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {TIMEZONE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value} className="bg-gray-800 text-white">
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-gray-400 text-sm mb-1">Time format</label>
                  <div className="flex gap-3">
                    {(['24h', '12h'] as const).map((fmt) => (
                    <button
                      key={fmt}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, timeFormat: fmt }))}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        form.timeFormat === fmt
                          ? 'bg-blue-600 text-white ring-2 ring-blue-400'
                          : 'bg-white/10 text-gray-300 hover:bg-white/15 hover:text-white'
                      }`}
                    >
                      {fmt === '24h' ? '24-hour' : '12-hour'}
                    </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className={cardClass}>
              <div className={cardTitleClass}>
                <SettingsIcon className="text-blue-400" size={20} />
                <h3 className="text-base font-semibold text-white">General</h3>
              </div>
              <p className="text-gray-500 text-sm">More user options can be added here (e.g. profile, notifications).</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
