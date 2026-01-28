/**
 * Weather API
 * API functions for weather information
 * Uses OpenWeatherMap API (free tier available).
 * Fallback wttr.in is CORS-blocked in browser; use VITE_OPENWEATHER_API_KEY or a backend proxy.
 */

import { apiRequest } from './client';
import { ApiResponse } from '@/types';

let openWeatherWarned = false;
let fallbackCorsWarned = false;

export interface WeatherData {
  temperature: number;
  description: string;
  icon: string;
  humidity: number;
  windSpeed: number;
  city: string;
  country: string;
}

/**
 * Get weather information
 * For now, we'll use a simple mock or fetch from a free weather API
 * You can integrate with OpenWeatherMap API by adding API key in environment variables
 */
export const getWeather = async (lat?: number, lng?: number): Promise<ApiResponse<WeatherData>> => {
  // Require coordinates - don't use default location
  if (!lat || !lng) {
    console.warn('Weather API called without coordinates');
    return {
      status: 'error',
      message: 'Location coordinates are required',
      data: {
        temperature: 0,
        description: 'Location required',
        icon: '01d',
        humidity: 0,
        windSpeed: 0,
        city: 'Unknown',
        country: '',
      },
    };
  }
  
  const apiKey = import.meta.env.VITE_OPENWEATHER_API_KEY;
  if (!apiKey && !openWeatherWarned) {
    openWeatherWarned = true;
    console.warn(
      'OpenWeatherMap API key not configured. Set VITE_OPENWEATHER_API_KEY in .env for weather. ' +
      'wttr.in fallback is blocked by CORS when called from the browser.'
    );
  }

  try {
    if (apiKey) {
      console.log('Fetching weather for coordinates:', { lat, lng });
      const response = await fetch(
        `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lng}&appid=${apiKey}&units=metric`
      );
      
      if (response.ok) {
        const data = await response.json();
        console.log('Weather data received:', data);
        return {
          status: 'success',
          data: {
            temperature: Math.round(data.main.temp),
            description: data.weather[0].description,
            icon: data.weather[0].icon,
            humidity: data.main.humidity,
            windSpeed: data.wind?.speed || 0,
            city: data.name,
            country: data.sys.country,
          },
        };
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Weather API error:', response.status, errorData);
      }
    }

    // Fallback: wttr.in is usually CORS-blocked from browser; skip to avoid repeated errors
    if (!fallbackCorsWarned) {
      fallbackCorsWarned = true;
      console.debug(
        '[Weather] Skipping wttr.in fallback (CORS blocks it from browser). Use VITE_OPENWEATHER_API_KEY or a backend proxy.'
      );
    }
    
    // Last resort: Return error
    return {
      status: 'error',
      message: 'Failed to fetch weather data',
      data: {
        temperature: 0,
        description: 'Unable to fetch',
        icon: '01d',
        humidity: 0,
        windSpeed: 0,
        city: 'Unknown',
        country: '',
      },
    };
  } catch (error) {
    console.error('Failed to fetch weather:', error);
    return {
      status: 'error',
      message: error instanceof Error ? error.message : 'Unknown error',
      data: {
        temperature: 0,
        description: 'Error',
        icon: '01d',
        humidity: 0,
        windSpeed: 0,
        city: 'Unknown',
        country: '',
      },
    };
  }
};

