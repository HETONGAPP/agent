/**
 * Settings API
 * GET /api/v1/settings/llm - current LLM config (server default, no API key).
 * GET/PUT /api/v1/settings/infrastructure - Redis, InfluxDB, MQTT, PostgreSQL.
 */

import { apiRequest } from './client';

export interface LLMSettingsServer {
  provider?: string;
  model?: string;
  ollama_url?: string;
}

export interface InfrastructureServer {
  redis: { host: string; port: number; db: number; password: string };
  influxdb: { url: string; org: string; bucket: string; token: string };
  postgresql: { host: string; port: number; database: string; user: string; password: string };
  mqtt: { broker_url: string; client_id: string; username: string; password: string };
}

export const getLLMSettings = async (): Promise<{
  status: string;
  data: LLMSettingsServer;
}> => {
  const res = await apiRequest<{ status: string; data: LLMSettingsServer }>({
    method: 'GET',
    url: '/api/v1/settings/llm',
  });
  return res as { status: string; data: LLMSettingsServer };
};

export const getInfrastructureSettings = async (): Promise<{
  status: string;
  data: InfrastructureServer;
}> => {
  const res = await apiRequest<{ status: string; data: InfrastructureServer }>({
    method: 'GET',
    url: '/api/v1/settings/infrastructure',
  });
  return res as { status: string; data: InfrastructureServer };
};

export const putInfrastructureSettings = async (data: {
  database?: {
    redis?: { host?: string; port?: number; db?: number; password?: string };
    influxdb?: { url?: string; org?: string; bucket?: string; token?: string };
    postgresql?: { host?: string; port?: number; database?: string; user?: string; password?: string };
  };
  mqtt?: { broker_url?: string; client_id?: string; username?: string; password?: string };
}): Promise<{ status: string; message?: string }> => {
  return apiRequest<{ status: string; message?: string }>({
    method: 'PUT',
    url: '/api/v1/settings/infrastructure',
    data,
  }) as Promise<{ status: string; message?: string }>;
};
