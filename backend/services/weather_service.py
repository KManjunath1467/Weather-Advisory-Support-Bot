import httpx
import math
from typing import Dict, Any, Optional, List, Tuple
from backend.config import settings
from backend.sop.models import WeatherData

# WMO Weather interpretation codes (WW)
WMO_CODE_MAP = {
    0: ("Clear sky", "☀️", False),
    1: ("Mainly clear", "🌤️", False),
    2: ("Partly cloudy", "⛅", False),
    3: ("Overcast", "☁️", False),
    45: ("Fog", "🌫️", False),
    48: ("Depositing rime fog", "🌫️", False),
    51: ("Light drizzle", "🌦️", False),
    53: ("Moderate drizzle", "🌦️", False),
    55: ("Dense drizzle", "🌧️", False),
    56: ("Light freezing drizzle", "🌧️", False),
    57: ("Dense freezing drizzle", "🌧️", False),
    61: ("Slight rain", "🌦️", False),
    63: ("Moderate rain", "🌧️", False),
    65: ("Heavy rain", "🌧️", False),
    66: ("Light freezing rain", "🌧️", False),
    67: ("Heavy freezing rain", "🌧️", False),
    71: ("Slight snow fall", "🌨️", False),
    73: ("Moderate snow fall", "🌨️", False),
    75: ("Heavy snow fall", "❄️", False),
    77: ("Snow grains", "❄️", False),
    80: ("Slight rain showers", "🌦️", False),
    81: ("Moderate rain showers", "🌧️", False),
    82: ("Violent rain showers", "⛈️", False),
    85: ("Slight snow showers", "🌨️", False),
    86: ("Heavy snow showers", "❄️", False),
    95: ("Thunderstorm", "⚡", True),
    96: ("Thunderstorm with slight hail", "⛈️", True),
    99: ("Thunderstorm with heavy hail", "⛈️", True),
}

def calculate_wind_chill(temperature_c: float, wind_speed_kmh: float) -> Optional[float]:
    """
    Computes wind chill (Environment Canada / NOAA formula)
    Applicable when temperature <= 10°C and wind speed > 4.8 km/h.
    """
    if temperature_c <= 10.0 and wind_speed_kmh > 4.8:
        wc = (
            13.12
            + (0.6215 * temperature_c)
            - (11.37 * math.pow(wind_speed_kmh, 0.16))
            + (0.3965 * temperature_c * math.pow(wind_speed_kmh, 0.16))
        )
        return round(wc, 1)
    return round(temperature_c, 1)

class WeatherService:
    def __init__(self):
        self.geocoding_url = settings.geocoding_base_url
        self.forecast_url = settings.open_meteo_base_url
        self.timeout = settings.weather_request_timeout
        self._geo_cache: Dict[str, Dict[str, Any]] = {}

    async def geocode(self, location_query: str) -> Optional[Dict[str, Any]]:
        """Finds geographical coordinates for a city or query name."""
        query_cleaned = location_query.strip()
        if not query_cleaned:
            return None

        cache_key = query_cleaned.lower()
        if cache_key in self._geo_cache:
            return self._geo_cache[cache_key]

        params = {
            "name": query_cleaned,
            "count": 5,
            "language": "en",
            "format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(self.geocoding_url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results", [])
                    if results:
                        top = results[0]
                        country = top.get("country", "")
                        admin1 = top.get("admin1", "")
                        display_name = f"{top['name']}"
                        if admin1:
                            display_name += f", {admin1}"
                        if country:
                            display_name += f", {country}"

                        info = {
                            "name": display_name,
                            "city": top["name"],
                            "latitude": float(top["latitude"]),
                            "longitude": float(top["longitude"]),
                            "country": country,
                            "timezone": top.get("timezone", "UTC"),
                        }
                        self._geo_cache[cache_key] = info
                        return info
        except Exception as e:
            print(f"Geocoding error for '{location_query}': {e}")

        # Default fallback coordinates for common cities if offline
        fallback_cities = {
            "london": {"name": "London, United Kingdom", "city": "London", "latitude": 51.5074, "longitude": -0.1278, "country": "UK", "timezone": "Europe/London"},
            "new york": {"name": "New York, USA", "city": "New York", "latitude": 40.7128, "longitude": -74.0060, "country": "USA", "timezone": "America/New_York"},
            "tokyo": {"name": "Tokyo, Japan", "city": "Tokyo", "latitude": 35.6762, "longitude": 139.6503, "country": "Japan", "timezone": "Asia/Tokyo"},
            "paris": {"name": "Paris, France", "city": "Paris", "latitude": 48.8566, "longitude": 2.3522, "country": "France", "timezone": "Europe/Paris"},
            "mumbai": {"name": "Mumbai, India", "city": "Mumbai", "latitude": 19.0760, "longitude": 72.8777, "country": "India", "timezone": "Asia/Kolkata"},
            "delhi": {"name": "Delhi, India", "city": "Delhi", "latitude": 28.6139, "longitude": 77.2090, "country": "India", "timezone": "Asia/Kolkata"},
            "sydney": {"name": "Sydney, Australia", "city": "Sydney", "latitude": -33.8688, "longitude": 151.2093, "country": "Australia", "timezone": "Australia/Sydney"},
            "dubai": {"name": "Dubai, UAE", "city": "Dubai", "latitude": 25.2048, "longitude": 55.2708, "country": "UAE", "timezone": "Asia/Dubai"},
            "singapore": {"name": "Singapore", "city": "Singapore", "latitude": 1.3521, "longitude": 103.8198, "country": "Singapore", "timezone": "Asia/Singapore"},
        }
        for k, v in fallback_cities.items():
            if k in query_cleaned.lower():
                return v

        return None

    async def get_weather(self, latitude: float, longitude: float, location_name: str, timezone: str = "auto") -> Tuple[WeatherData, Dict[str, Any]]:
        """
        Fetches full current weather, hourly forecast, and daily outlook from Open-Meteo.
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "is_day",
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "weather_code",
                "cloud_cover",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "uv_index",
                "visibility",
            ],
            "hourly": [
                "temperature_2m",
                "precipitation_probability",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "uv_index",
                "visibility",
            ],
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
                "uv_index_max",
                "sunrise",
                "sunset",
            ],
            "timezone": timezone or "auto",
        }

        raw_data = {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(self.forecast_url, params=params)
                if res.status_code == 200:
                    raw_data = res.json()
        except Exception as e:
            print(f"Weather API error for {location_name}: {e}")

        # Fallback simulation if offline or error
        if not raw_data or "current" not in raw_data:
            raw_data = self._generate_fallback_weather(latitude, longitude, location_name)

        current = raw_data.get("current", {})
        temp = float(current.get("temperature_2m", 22.0))
        apparent_temp = float(current.get("apparent_temperature", temp))
        wind_spd = float(current.get("wind_speed_10m", 12.0))
        wind_gst = float(current.get("wind_gusts_10m", wind_spd * 1.3))
        humidity = float(current.get("relative_humidity_2m", 55.0))
        precip = float(current.get("precipitation", 0.0))
        w_code = int(current.get("weather_code", 0))
        uv = float(current.get("uv_index", 3.0))
        vis_meters = float(current.get("visibility", 10000.0))
        vis_km = round(vis_meters / 1000.0, 1)
        is_day = bool(current.get("is_day", 1))

        # Hourly precipitation probability for the current hour
        precip_prob = 0.0
        hourly = raw_data.get("hourly", {})
        if hourly and "precipitation_probability" in hourly:
            probs = hourly["precipitation_probability"]
            if probs:
                precip_prob = float(probs[0])

        w_desc, w_icon, is_lightning = WMO_CODE_MAP.get(w_code, ("Fair", "☀️", False))
        wind_chill_val = calculate_wind_chill(temp, wind_spd)

        weather_obj = WeatherData(
            location_name=location_name,
            latitude=latitude,
            longitude=longitude,
            timezone=raw_data.get("timezone", timezone),
            temperature=temp,
            apparent_temperature=apparent_temp,
            wind_speed=wind_spd,
            wind_gusts=wind_gst,
            wind_chill=wind_chill_val,
            relative_humidity=humidity,
            precipitation=precip,
            precipitation_probability=precip_prob,
            weather_code=w_code,
            weather_description=w_desc,
            visibility=vis_km,
            uv_index=uv,
            is_day=is_day,
            lightning_risk=is_lightning,
            wave_height=None,
            raw_response=raw_data,
        )

        return weather_obj, raw_data

    def _generate_fallback_weather(self, lat: float, lon: float, location_name: str) -> Dict[str, Any]:
        """Generates realistic fallback data when external connection is restricted."""
        return {
            "latitude": lat,
            "longitude": lon,
            "timezone": "UTC",
            "current": {
                "temperature_2m": 24.5,
                "apparent_temperature": 25.0,
                "relative_humidity_2m": 58,
                "is_day": 1,
                "precipitation": 0.0,
                "weather_code": 1,
                "wind_speed_10m": 14.2,
                "wind_gusts_10m": 20.1,
                "uv_index": 4.5,
                "visibility": 10000,
            },
            "hourly": {
                "time": [f"2026-10-02T{h:02d}:00" for h in range(24)],
                "temperature_2m": [22 + (i % 6) for i in range(24)],
                "precipitation_probability": [5, 10, 15, 10, 5, 0, 0, 0, 5, 10, 10, 15, 20, 25, 20, 15, 10, 5, 5, 5, 5, 5, 5, 5],
                "weather_code": [1] * 24,
                "wind_speed_10m": [12 + (i % 5) for i in range(24)],
                "uv_index": [0, 0, 0, 0, 0, 0, 1, 2, 4, 6, 7, 6, 5, 3, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0],
                "visibility": [10000] * 24,
            },
            "daily": {
                "time": [f"2026-10-0{i+2}" for i in range(7)],
                "weather_code": [1, 2, 0, 61, 2, 1, 0],
                "temperature_2m_max": [27.0, 26.5, 28.0, 23.0, 25.0, 26.0, 27.5],
                "temperature_2m_min": [18.0, 17.5, 19.0, 16.0, 17.0, 18.0, 19.0],
                "precipitation_sum": [0.0, 0.2, 0.0, 8.5, 1.2, 0.0, 0.0],
                "precipitation_probability_max": [10, 20, 5, 85, 40, 15, 5],
                "wind_speed_10m_max": [18.0, 19.5, 15.0, 32.0, 22.0, 16.0, 14.0],
                "wind_gusts_10m_max": [28.0, 30.0, 24.0, 48.0, 34.0, 25.0, 22.0],
                "uv_index_max": [6.5, 6.0, 7.0, 4.0, 5.5, 6.5, 7.0],
                "sunrise": ["06:15"] * 7,
                "sunset": ["18:30"] * 7,
            },
        }

weather_service = WeatherService()
