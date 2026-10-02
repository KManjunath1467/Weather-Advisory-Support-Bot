from typing import Optional, Dict, Any, List
from backend.services.weather_service import weather_service
from backend.services.intent_service import intent_service
from backend.services.llm_service import llm_service
from backend.sop.engine import SOPEngine
from backend.sop.models import WeatherData

sop_engine = SOPEngine()

class AdvisorService:
    def __init__(self):
        self.weather_svc = weather_service
        self.intent_svc = intent_service
        self.llm_svc = llm_service
        self.sop_eng = sop_engine

    async def get_advice_for_query(
        self,
        query: str,
        override_location: Optional[str] = None,
        override_activity: Optional[str] = None,
        target_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        End-to-end processing pipeline for natural language query:
        1. Parse intent, location, activity, demographics
        2. Geocode location & fetch weather telemetry
        3. Evaluate deterministic SOP conditions
        4. Synthesize advisory & safety response
        """
        # 1. Intent Extraction
        intent = self.intent_svc.extract_intent(query, default_location=override_location)
        if override_activity:
            intent.activity = override_activity
        if override_location:
            intent.location = override_location
        if target_groups:
            intent.vulnerable_groups = list(set(intent.vulnerable_groups + target_groups))

        # Determine location to query
        target_location = intent.location or "London"

        # 2. Geocode
        geo_info = await self.weather_svc.geocode(target_location)
        if not geo_info:
            # Fallback to London if geocoding yields no results
            geo_info = {
                "name": target_location.title(),
                "city": target_location.title(),
                "latitude": 51.5074,
                "longitude": -0.1278,
                "country": "Global",
                "timezone": "UTC",
            }

        # 3. Weather Fetch
        weather_obj, raw_weather = await self.weather_svc.get_weather(
            latitude=geo_info["latitude"],
            longitude=geo_info["longitude"],
            location_name=geo_info["name"],
            timezone=geo_info.get("timezone", "auto"),
        )

        # 4. SOP Rule Evaluation
        matched_sops = self.sop_eng.evaluate(
            weather=weather_obj,
            activity=intent.activity,
            target_groups=intent.vulnerable_groups,
        )

        # 5. LLM Advisory Synthesis
        advisory_payload = self.llm_svc.generate_advisory(
            query=query,
            intent=intent,
            weather=weather_obj,
            matched_sops=matched_sops,
        )

        # Format hourly and daily forecasts for frontend visualization
        hourly_data = []
        raw_hourly = raw_weather.get("hourly", {})
        if raw_hourly and "time" in raw_hourly:
            times = raw_hourly.get("time", [])[:24]
            temps = raw_hourly.get("temperature_2m", [])[:24]
            probs = raw_hourly.get("precipitation_probability", [])[:24]
            w_codes = raw_hourly.get("weather_code", [])[:24]
            winds = raw_hourly.get("wind_speed_10m", [])[:24]
            uvs = raw_hourly.get("uv_index", [])[:24]
            for i in range(len(times)):
                t_str = times[i].split("T")[-1] if "T" in times[i] else f"{i:02d}:00"
                hourly_data.append({
                    "time": t_str,
                    "temperature": temps[i] if i < len(temps) else weather_obj.temperature,
                    "precip_prob": probs[i] if i < len(probs) else 0,
                    "weather_code": w_codes[i] if i < len(w_codes) else weather_obj.weather_code,
                    "wind_speed": winds[i] if i < len(winds) else weather_obj.wind_speed,
                    "uv_index": uvs[i] if i < len(uvs) else 0,
                })

        daily_data = []
        raw_daily = raw_weather.get("daily", {})
        if raw_daily and "time" in raw_daily:
            d_times = raw_daily.get("time", [])[:7]
            t_max = raw_daily.get("temperature_2m_max", [])[:7]
            t_min = raw_daily.get("temperature_2m_min", [])[:7]
            d_codes = raw_daily.get("weather_code", [])[:7]
            d_probs = raw_daily.get("precipitation_probability_max", [])[:7]
            d_winds = raw_daily.get("wind_speed_10m_max", [])[:7]
            for i in range(len(d_times)):
                daily_data.append({
                    "date": d_times[i],
                    "temp_max": t_max[i] if i < len(t_max) else weather_obj.temperature + 3,
                    "temp_min": t_min[i] if i < len(t_min) else weather_obj.temperature - 4,
                    "weather_code": d_codes[i] if i < len(d_codes) else weather_obj.weather_code,
                    "precip_prob": d_probs[i] if i < len(d_probs) else 0,
                    "wind_speed": d_winds[i] if i < len(d_winds) else weather_obj.wind_speed,
                })

        return {
            "query": query,
            "intent": intent.model_dump(),
            "location": geo_info,
            "weather": weather_obj.model_dump(exclude={"raw_response"}),
            "hourly_forecast": hourly_data,
            "daily_forecast": daily_data,
            "advisory": advisory_payload,
        }

advisor_service = AdvisorService()
