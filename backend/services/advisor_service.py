from typing import Optional, Dict, Any, List
from backend.graph.agent import advisor_graph
from backend.graph.state import AdvisorState
from backend.memory.session_store import session_store

class AdvisorService:
    async def process_chat(
        self,
        query: str,
        session_id: Optional[str] = "default",
        location: Optional[str] = None,
        activity: Optional[str] = None,
        vulnerable_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the LangGraph Agent for a conversational outdoor safety query.
        """
        session_id = session_id or "default"
        
        # If user explicitly supplied location/activity in request body, seed/update session
        if location:
            session_store.update(session_id, location=location)
        if activity:
            session_store.update(session_id, activity=activity)
        if vulnerable_groups:
            session_store.update(session_id, vulnerable_groups=vulnerable_groups)

        session = session_store.get_or_create(session_id)

        # Initial state for LangGraph
        initial_state: AdvisorState = {
            "session_id": session_id,
            "user_query": query,
            "conversation_history": session.history,
            "intent": None,
            "location": location or session.location,
            "location_resolved": False,
            "latitude": session.latitude,
            "longitude": session.longitude,
            "weather": None,
            "raw_weather": None,
            "weather_available": False,
            "matched_sops": [],
            "selected_sop": None,
            "sop_found": False,
            "conflict_resolution": None,
            "adversarial_attempt": False,
            "error": None,
            "final_response": "",
        }

        # Invoke LangGraph StateGraph
        final_state = await advisor_graph.ainvoke(initial_state)

        # Record history
        session_store.add_history(session_id, "user", query)
        session_store.add_history(session_id, "assistant", final_state.get("final_response", ""))

        # Format hourly and daily forecasts if live weather was successfully retrieved
        hourly_data = []
        daily_data = []
        raw_weather = final_state.get("raw_weather")
        weather_dict = final_state.get("weather")

        if raw_weather:
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
                        "temperature": temps[i] if i < len(temps) else (weather_dict.get("temperature") if weather_dict else 0),
                        "precip_prob": probs[i] if i < len(probs) else 0,
                        "weather_code": w_codes[i] if i < len(w_codes) else 0,
                        "wind_speed": winds[i] if i < len(winds) else 0,
                        "uv_index": uvs[i] if i < len(uvs) else 0,
                    })

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
                        "temp_max": t_max[i] if i < len(t_max) else 0,
                        "temp_min": t_min[i] if i < len(t_min) else 0,
                        "weather_code": d_codes[i] if i < len(d_codes) else 0,
                        "precip_prob": d_probs[i] if i < len(d_probs) else 0,
                        "wind_speed": d_winds[i] if i < len(d_winds) else 0,
                    })

        return {
            "session_id": session_id,
            "response": final_state.get("final_response", ""),
            "intent": final_state.get("intent"),
            "location": {
                "name": final_state.get("location"),
                "latitude": final_state.get("latitude"),
                "longitude": final_state.get("longitude"),
            } if final_state.get("location_resolved") else None,
            "weather": weather_dict,
            "matched_sops": final_state.get("matched_sops", []),
            "selected_sop": final_state.get("selected_sop"),
            "conflict_resolution": final_state.get("conflict_resolution"),
            "sop_found": final_state.get("sop_found", False),
            "error": final_state.get("error"),
            "hourly_forecast": hourly_data,
            "daily_forecast": daily_data,
        }

advisor_service = AdvisorService()
