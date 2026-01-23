/**
 * Geocoding utilities
 * Reverse geocoding using Nominatim API (OpenStreetMap)
 */

export interface ReverseGeocodeResult {
  country: string;
  state?: string;
  province?: string;
  city?: string;
  address?: string;
  timezone?: string;
}

/**
 * Reverse geocode coordinates to get location information
 * Uses Nominatim API (OpenStreetMap) - free, no API key required
 * 
 * @param lat Latitude
 * @param lng Longitude
 * @returns Location information including country and state/province
 */
export async function reverseGeocode(
  lat: number,
  lng: number
): Promise<ReverseGeocodeResult | null> {
  try {
    // Use Nominatim API for reverse geocoding
    // Rate limit: 1 request per second (we'll add a small delay)
    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&addressdetails=1&zoom=10`;
    
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'DataCenterMap/1.0', // Required by Nominatim
      },
    });

    if (!response.ok) {
      console.warn('[Geocoding] Failed to fetch reverse geocode:', response.status);
      return null;
    }

    const data = await response.json();
    
    if (!data || !data.address) {
      console.warn('[Geocoding] No address data in response');
      return null;
    }

    const address = data.address;
    
    // Extract country
    const country = address.country || address.country_code?.toUpperCase() || '';
    
    // Extract state/province (different countries use different fields)
    const state = 
      address.state || 
      address.province || 
      address.region || 
      address.state_district || 
      '';
    
    // Extract city
    const city = 
      address.city || 
      address.town || 
      address.village || 
      address.municipality || 
      '';
    
    // Build address string
    const addressParts = [];
    if (city) addressParts.push(city);
    if (state) addressParts.push(state);
    if (country) addressParts.push(country);
    const addressString = addressParts.join(', ');

    // Get timezone based on coordinates and location
    const timezone = await getTimezoneFromCoordinates(lat, lng, country, state);

    return {
      country: country || '',
      state: state || undefined,
      province: state || undefined,
      city: city || undefined,
      address: addressString || undefined,
      timezone: timezone || undefined,
    };
  } catch (error) {
    console.error('[Geocoding] Error during reverse geocoding:', error);
    return null;
  }
}

/**
 * Get timezone from coordinates and location
 * Uses a combination of coordinate-based lookup and location-based mapping
 */
async function getTimezoneFromCoordinates(
  lat: number,
  lng: number,
  country?: string,
  state?: string
): Promise<string | null> {
  try {
    // First, try to use a timezone API (free tier available)
    // Using TimeZoneDB API (free, no API key required for basic usage)
    // Alternative: Use Google Time Zone API (requires API key)
    
    // For now, use a coordinate-based lookup with location mapping
    const timezone = lookupTimezoneByLocation(lat, lng, country, state);
    
    if (timezone) {
      return timezone;
    }

    // Fallback: Use a simple coordinate-based timezone estimation
    // This is a simplified approach - for production, consider using a proper timezone library
    return estimateTimezoneFromCoordinates(lat, lng);
  } catch (error) {
    console.warn('[Geocoding] Error getting timezone:', error);
    return null;
  }
}

/**
 * Lookup timezone based on location (country, state) and coordinates
 * Uses detailed mapping for US, Canada, and Mexico
 */
function lookupTimezoneByLocation(
  lat: number,
  lng: number,
  country?: string,
  state?: string
): string | null {
  const normalizedCountry = country?.toLowerCase().trim() || '';
  const normalizedState = state?.toLowerCase().trim() || '';

  // United States timezone mapping
  if (normalizedCountry.includes('united states') || normalizedCountry === 'usa' || normalizedCountry === 'us') {
    const usTimezoneMap: Record<string, string> = {
      'alabama': 'America/Chicago',
      'alaska': 'America/Anchorage',
      'arizona': 'America/Phoenix',
      'arkansas': 'America/Chicago',
      'california': 'America/Los_Angeles',
      'colorado': 'America/Denver',
      'connecticut': 'America/New_York',
      'delaware': 'America/New_York',
      'florida': 'America/New_York', // Most of Florida is Eastern, but panhandle is Central
      'georgia': 'America/New_York',
      'hawaii': 'Pacific/Honolulu',
      'idaho': 'America/Denver', // Most of Idaho is Mountain, but northern part is Pacific
      'illinois': 'America/Chicago',
      'indiana': 'America/Indiana/Indianapolis', // Most of Indiana is Eastern
      'iowa': 'America/Chicago',
      'kansas': 'America/Chicago', // Most of Kansas is Central, but western part is Mountain
      'kentucky': 'America/New_York', // Most of Kentucky is Eastern, but western part is Central
      'louisiana': 'America/Chicago',
      'maine': 'America/New_York',
      'maryland': 'America/New_York',
      'massachusetts': 'America/New_York',
      'michigan': 'America/Detroit', // Most of Michigan is Eastern, but western part is Central
      'minnesota': 'America/Chicago',
      'mississippi': 'America/Chicago',
      'missouri': 'America/Chicago',
      'montana': 'America/Denver',
      'nebraska': 'America/Chicago', // Most of Nebraska is Central, but western part is Mountain
      'nevada': 'America/Los_Angeles',
      'new hampshire': 'America/New_York',
      'new jersey': 'America/New_York',
      'new mexico': 'America/Denver',
      'new york': 'America/New_York',
      'north carolina': 'America/New_York',
      'north dakota': 'America/Chicago', // Most of North Dakota is Central, but western part is Mountain
      'ohio': 'America/New_York',
      'oklahoma': 'America/Chicago',
      'oregon': 'America/Los_Angeles', // Most of Oregon is Pacific, but eastern part is Mountain
      'pennsylvania': 'America/New_York',
      'rhode island': 'America/New_York',
      'south carolina': 'America/New_York',
      'south dakota': 'America/Chicago', // Most of South Dakota is Central, but western part is Mountain
      'tennessee': 'America/Chicago', // Most of Tennessee is Central, but eastern part is Eastern
      'texas': 'America/Chicago', // Most of Texas is Central, but western part is Mountain
      'utah': 'America/Denver',
      'vermont': 'America/New_York',
      'virginia': 'America/New_York',
      'washington': 'America/Los_Angeles',
      'west virginia': 'America/New_York',
      'wisconsin': 'America/Chicago',
      'wyoming': 'America/Denver',
      // State abbreviations
      'al': 'America/Chicago',
      'ak': 'America/Anchorage',
      'az': 'America/Phoenix',
      'ar': 'America/Chicago',
      'ca': 'America/Los_Angeles',
      'co': 'America/Denver',
      'ct': 'America/New_York',
      'de': 'America/New_York',
      'fl': 'America/New_York',
      'ga': 'America/New_York',
      'hi': 'Pacific/Honolulu',
      'id': 'America/Denver',
      'il': 'America/Chicago',
      'in': 'America/Indiana/Indianapolis',
      'ia': 'America/Chicago',
      'ks': 'America/Chicago',
      'ky': 'America/New_York',
      'la': 'America/Chicago',
      'me': 'America/New_York',
      'md': 'America/New_York',
      'ma': 'America/New_York',
      'mi': 'America/Detroit',
      'mn': 'America/Chicago',
      'ms': 'America/Chicago',
      'mo': 'America/Chicago',
      'mt': 'America/Denver',
      'ne': 'America/Chicago',
      'nv': 'America/Los_Angeles',
      'nh': 'America/New_York',
      'nj': 'America/New_York',
      'nm': 'America/Denver',
      'ny': 'America/New_York',
      'nc': 'America/New_York',
      'nd': 'America/Chicago',
      'oh': 'America/New_York',
      'ok': 'America/Chicago',
      'or': 'America/Los_Angeles',
      'pa': 'America/New_York',
      'ri': 'America/New_York',
      'sc': 'America/New_York',
      'sd': 'America/Chicago',
      'tn': 'America/Chicago',
      'tx': 'America/Chicago',
      'ut': 'America/Denver',
      'vt': 'America/New_York',
      'va': 'America/New_York',
      'wa': 'America/Los_Angeles',
      'wv': 'America/New_York',
      'wi': 'America/Chicago',
      'wy': 'America/Denver',
    };

    // Try to match by state name or abbreviation
    for (const [key, tz] of Object.entries(usTimezoneMap)) {
      if (normalizedState.includes(key) || normalizedState === key) {
        return tz;
      }
    }
  }

  // Canada timezone mapping
  if (normalizedCountry === 'canada') {
    const canadaTimezoneMap: Record<string, string> = {
      'alberta': 'America/Edmonton',
      'british columbia': 'America/Vancouver',
      'manitoba': 'America/Winnipeg',
      'new brunswick': 'America/Moncton',
      'newfoundland and labrador': 'America/St_Johns',
      'northwest territories': 'America/Yellowknife',
      'nova scotia': 'America/Halifax',
      'nunavut': 'America/Iqaluit',
      'ontario': 'America/Toronto',
      'prince edward island': 'America/Halifax',
      'quebec': 'America/Montreal',
      'saskatchewan': 'America/Regina',
      'yukon': 'America/Whitehorse',
      // Province abbreviations
      'ab': 'America/Edmonton',
      'bc': 'America/Vancouver',
      'mb': 'America/Winnipeg',
      'nb': 'America/Moncton',
      'nl': 'America/St_Johns',
      'nt': 'America/Yellowknife',
      'ns': 'America/Halifax',
      'nu': 'America/Iqaluit',
      'on': 'America/Toronto',
      'pe': 'America/Halifax',
      'qc': 'America/Montreal',
      'sk': 'America/Regina',
      'yt': 'America/Whitehorse',
    };

    for (const [key, tz] of Object.entries(canadaTimezoneMap)) {
      if (normalizedState.includes(key) || normalizedState === key) {
        return tz;
      }
    }
  }

  // Mexico timezone mapping
  if (normalizedCountry === 'mexico') {
    // Most of Mexico uses America/Mexico_City
    // But some border states use US timezones
    if (normalizedState.includes('baja california')) {
      return 'America/Tijuana'; // Pacific Time
    }
    return 'America/Mexico_City'; // Central Time (most of Mexico)
  }

  return null;
}

/**
 * Estimate timezone from coordinates (fallback method)
 * This is a simplified approach - for production, consider using a proper timezone library
 */
function estimateTimezoneFromCoordinates(lat: number, lng: number): string | null {
  // Simple timezone estimation based on longitude
  // This is approximate and may not be accurate for all locations
  // US timezones (approximate longitude ranges):
  // Eastern: -75 to -85
  // Central: -85 to -100
  // Mountain: -100 to -115
  // Pacific: -115 to -125
  
  if (lng >= -85 && lng <= -65) {
    return 'America/New_York'; // Eastern Time
  } else if (lng >= -100 && lng < -85) {
    return 'America/Chicago'; // Central Time
  } else if (lng >= -115 && lng < -100) {
    return 'America/Denver'; // Mountain Time
  } else if (lng >= -125 && lng < -115) {
    return 'America/Los_Angeles'; // Pacific Time
  } else if (lng < -125) {
    return 'America/Anchorage'; // Alaska Time
  } else if (lng >= -160 && lng < -155) {
    return 'Pacific/Honolulu'; // Hawaii Time
  }

  // Default to UTC if we can't determine
  return 'UTC';
}

/**
 * Normalize country name to match form options
 * Maps common country names to form values
 */
export function normalizeCountryName(country: string): string {
  const countryMap: Record<string, string> = {
    'united states': 'United States',
    'usa': 'United States',
    'us': 'United States',
    'united states of america': 'United States',
    'canada': 'Canada',
    'mexico': 'Mexico',
  };

  const normalized = country.toLowerCase().trim();
  return countryMap[normalized] || country;
}

