from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.sop.models import SOPMatchResult, WeatherData, IntentExtraction

class LLMService:
    """
    SOP-Grounded LLM formatting service.
    Guarantees that all advice is 100% grounded in verified SOP rules.
    """

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.temperature = settings.llm_temperature

    def format_sop_advisory(
        self,
        intent: IntentExtraction,
        weather: WeatherData,
        matched_sops: List[SOPMatchResult],
        conflict_resolution: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes a strictly SOP-grounded response citing exact SOP IDs,
        observed weather parameters, conditions, and required actions.
        """
        if not matched_sops:
            act = intent.activity or "this activity"
            loc = weather.location_name
            return {
                "sop_found": False,
                "advisory_markdown": (
                    f"No applicable SOP was found for {act} under the current weather conditions in {loc} "
                    f"(Temperature: {weather.temperature}°C, Wind: {weather.wind_speed} km/h, Weather: {weather.weather_description}). "
                    f"I therefore cannot provide a policy-backed safety recommendation."
                ),
            }

        selected = matched_sops[0].sop
        activity_title = (intent.activity or "Outdoor Activity").title()

        lines = [
            f"## 🛡️ SOP Safety Advisory: **{activity_title}** in **{weather.location_name}**\n",
            f"**Observed Weather Telemetry:** {weather.weather_description} | "
            f"🌡️ {weather.temperature}°C (Feels like {weather.apparent_temperature}°C) | "
            f"💨 Wind {weather.wind_speed} km/h (Gusts: {weather.wind_gusts} km/h) | "
            f"💧 Humidity {weather.relative_humidity}% | "
            f"☀️ UV Index {weather.uv_index}\n",
            f"### Primary Policy Applied: **[{selected.id}] {selected.name}**",
            f"- **Severity Level:** `{selected.severity}` (Priority: `{selected.priority}`)",
            f"- **Triggered Condition:** {matched_sops[0].reason}",
            f"- **Mandatory Directive:** {selected.advisory}",
            f"- **Required Action:** **{selected.recommended_action}**\n",
        ]

        if conflict_resolution:
            lines.append(f"### ⚖️ Conflict Resolution\n> {conflict_resolution}\n")

        return {
            "sop_found": True,
            "selected_sop": selected.model_dump(),
            "advisory_markdown": "\n".join(lines),
        }

llm_service = LLMService()
