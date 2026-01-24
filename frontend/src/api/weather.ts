/**
 * Weather API
 * API functions for weather information
 * Uses OpenWeatherMap API (free tier available)
 */

import { apiRequest } from './client';
import { ApiResponse } from '@/types';

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
  
  try {
    // Try to get weather from OpenWeatherMap (requires API key)
    const apiKey = import.meta.env.VITE_OPENWEATHER_API_KEY;
    
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
    } else {
      console.warn('OpenWeatherMap API key not configured. Using fallback weather service.');
    }
    
    // Fallback: Try using a free weather API (wttr.in) as backup
    try {
      const fallbackResponse = await fetch(
        `https://wttr.in/?format=j1&lat=${lat}&lon=${lng}`
      );
      
      if (fallbackResponse.ok) {
        const data = await fallbackResponse.json();
        const current = data.current_condition[0];
        return {
          status: 'success',
          data: {
            temperature: parseInt(current.temp_C),
            description: current.weatherDesc[0].value,
            icon: '01d', // wttr.in doesn't provide icon codes, use default
            humidity: parseInt(current.humidity),
            windSpeed: parseFloat(current.windspeedKmph) / 3.6, // Convert km/h to m/s
            city: data.nearest_area[0].areaName[0].value,
            country: data.nearest_area[0].country[0].value,
          },
        };
      }
    } catch (fallbackError) {
      console.error('Fallback weather API failed:', fallbackError);
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

