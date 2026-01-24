/**
 * Application Configuration
 * Centralized configuration to avoid hardcoding
 */

export interface AppConfig {
  api: {
    baseUrl: string;
    timeout: number;
  };
  features: {
    realTimeUpdates: boolean;
    enableNotifications: boolean;
    enableExport: boolean;
  };
  ui: {
    theme: 'light' | 'dark' | 'auto';
    itemsPerPage: number;
    maxItemsPerPage: number;
  };
  flow: {
    nodeSpacing: number;
    minZoom: number;
    maxZoom: number;
    defaultZoom: number;
  };
}

const defaultConfig: AppConfig = {
  api: {
    baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    timeout: 300000, // 5 minutes (300 seconds) - increased for long-running diagnostic tasks
  },
  features: {
    realTimeUpdates: true,
    enableNotifications: true,
    enableExport: true,
  },
  ui: {
    theme: 'dark',
    itemsPerPage: 20,
    maxItemsPerPage: 100,
  },
  flow: {
    nodeSpacing: 150,
    minZoom: 0.1,
    maxZoom: 2,
    defaultZoom: 1,
  },
};

/**
 * Get application configuration
 * Can be overridden by environment variables
 */
export const getAppConfig = (): AppConfig => {
  return {
    ...defaultConfig,
    api: {
      baseUrl: import.meta.env.VITE_API_BASE_URL || defaultConfig.api.baseUrl,
      timeout: Number(import.meta.env.VITE_API_TIMEOUT) || defaultConfig.api.timeout,
    },
    features: {
      realTimeUpdates: import.meta.env.VITE_ENABLE_REALTIME !== 'false',
      enableNotifications: import.meta.env.VITE_ENABLE_NOTIFICATIONS !== 'false',
      enableExport: import.meta.env.VITE_ENABLE_EXPORT !== 'false',
    },
    ui: {
      theme: (import.meta.env.VITE_THEME as 'light' | 'dark' | 'auto') || defaultConfig.ui.theme,
      itemsPerPage: Number(import.meta.env.VITE_ITEMS_PER_PAGE) || defaultConfig.ui.itemsPerPage,
      maxItemsPerPage: Number(import.meta.env.VITE_MAX_ITEMS_PER_PAGE) || defaultConfig.ui.maxItemsPerPage,
    },
  };
};

export const appConfig = getAppConfig();












