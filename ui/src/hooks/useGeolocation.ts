import { useState, useEffect } from 'react';
import type { BrowserGeoLocation } from '../services/api';

interface GeolocationState {
  location: BrowserGeoLocation | null;
  locationName: string | null;
  error: string | null;
  loading: boolean;
}

/**
 * Custom hook to get user's current geolocation
 * Uses browser's Geolocation API
 */
export function useGeolocation() {
  const [state, setState] = useState<GeolocationState>({
    location: null,
    locationName: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    if (!navigator.geolocation) {
      setState({
        location: null,
        locationName: null,
        error: 'Geolocation is not supported by your browser',
        loading: false,
      });
      return;
    }

    const successHandler = async (position: GeolocationPosition) => {
      const location: BrowserGeoLocation = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
      };

      // Update with coordinates first
      setState({
        location,
        locationName: null,
        error: null,
        loading: true, // Still loading the city name
      });

      // Reverse geocode to get city name
      try {
        const response = await fetch(
          `https://nominatim.openstreetmap.org/reverse?lat=${location.latitude}&lon=${location.longitude}&format=json`,
          {
            headers: {
              'User-Agent': 'FastFoodOrderingAgent/1.0'
            }
          }
        );

        if (response.ok) {
          const data = await response.json();
          const city = data.address?.city || data.address?.town || data.address?.village || data.address?.county;
          const state = data.address?.state;

          let locationName = '';
          if (city && state) {
            // Abbreviate state if it's in the US
            const stateAbbrev = getStateAbbreviation(state);
            locationName = `${city}, ${stateAbbrev || state}`;
          } else if (city) {
            locationName = city;
          } else if (state) {
            locationName = state;
          } else {
            locationName = `${location.latitude.toFixed(2)}, ${location.longitude.toFixed(2)}`;
          }

          setState({
            location,
            locationName,
            error: null,
            loading: false,
          });
        } else {
          // Fallback to coordinates if geocoding fails
          setState({
            location,
            locationName: `${location.latitude.toFixed(2)}, ${location.longitude.toFixed(2)}`,
            error: null,
            loading: false,
          });
        }
      } catch (error) {
        // Fallback to coordinates if geocoding fails
        setState({
          location,
          locationName: `${location.latitude.toFixed(2)}, ${location.longitude.toFixed(2)}`,
          error: null,
          loading: false,
        });
      }
    };

    const errorHandler = (error: GeolocationPositionError) => {
      let errorMessage = 'Unable to retrieve your location';

      switch (error.code) {
        case error.PERMISSION_DENIED:
          errorMessage = 'Location permission denied. Please enable location access.';
          break;
        case error.POSITION_UNAVAILABLE:
          errorMessage = 'Location information is unavailable.';
          break;
        case error.TIMEOUT:
          errorMessage = 'Location request timed out.';
          break;
      }

      setState({
        location: null,
        locationName: null,
        error: errorMessage,
        loading: false,
      });
    };

    navigator.geolocation.getCurrentPosition(successHandler, errorHandler, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    });
  }, []);

  return state;
}

// Helper function to abbreviate US state names
function getStateAbbreviation(stateName: string): string | null {
  const states: Record<string, string> = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
    'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
    'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY'
  };

  return states[stateName] || null;
}
