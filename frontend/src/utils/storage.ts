/**
 * Local Storage Utility Functions
 * Helper functions for localStorage operations
 */

import { STORAGE_KEYS } from '@/config/constants';

/**
 * Get item from localStorage
 */
export const getStorageItem = <T>(key: string, defaultValue: T): T => {
  try {
    const item = localStorage.getItem(key);
    if (item) {
      return JSON.parse(item) as T;
    }
  } catch (error) {
    console.error(`Error reading from localStorage key "${key}":`, error);
  }
  return defaultValue;
};

/**
 * Set item to localStorage
 */
export const setStorageItem = <T>(key: string, value: T): void => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.error(`Error writing to localStorage key "${key}":`, error);
  }
};

/**
 * Remove item from localStorage
 */
export const removeStorageItem = (key: string): void => {
  try {
    localStorage.removeItem(key);
  } catch (error) {
    console.error(`Error removing from localStorage key "${key}":`, error);
  }
};

/**
 * Clear all localStorage items
 */
export const clearStorage = (): void => {
  try {
    localStorage.clear();
  } catch (error) {
    console.error('Error clearing localStorage:', error);
  }
};

/**
 * Get theme from storage
 */
export const getTheme = (): 'light' | 'dark' | 'auto' => {
  return getStorageItem(STORAGE_KEYS.THEME, 'dark');
};

/**
 * Set theme to storage
 */
export const setTheme = (theme: 'light' | 'dark' | 'auto'): void => {
  setStorageItem(STORAGE_KEYS.THEME, theme);
};














