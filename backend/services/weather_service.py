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
        """
        Resolves geographical coordinates for a city or query name strictly using Open-Meteo Geocoding.
        Returns None if unresolved without any fabricated fallbacks.
        """
        if not location_query:
            return None

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

        # Return None when geocoding fails - NO fabricated city fallbacks!
        return None

    async def get_weather(
        self, latitude: float, longitude: float, location_name: str, timezone: str = "auto"
    ) -> Tuple[Optional[WeatherData], Optional[Dict[str, Any]]]:
        """
        Fetches live current weather, hourly forecast, and daily outlook from Open-Meteo.
        Returns (None, None) if live API retrieval fails. No synthetic numbers are generated.
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

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(self.forecast_url, params=params)
                if res.status_code == 200:
                    raw_data = res.json()
                    current = raw_data.get("current")
                    if current:
                        temp = float(current.get("temperature_2m", 0.0))
                        apparent_temp = float(current.get("apparent_temperature", temp))
                        wind_spd = float(current.get("wind_speed_10m", 0.0))
                        wind_gst = float(current.get("wind_gusts_10m", wind_spd))
                        humidity = float(current.get("relative_humidity_2m", 0.0))
                        precip = float(current.get("precipitation", 0.0))
                        w_code = int(current.get("weather_code", 0))
                        uv = float(current.get("uv_index", 0.0))
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
        except Exception as e:
            print(f"Weather API error for {location_name}: {e}")

        # Strict failure: return (None, None) so LangGraph branches to weather_error
        return None, None

weather_service = WeatherService()
