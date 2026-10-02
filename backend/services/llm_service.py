import os
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.sop.models import SOPMatchResult, WeatherData, IntentExtraction

class LLMService:
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.temperature = settings.llm_temperature

    def calculate_safety_score(self, weather: WeatherData, matched_sops: List[SOPMatchResult]) -> int:
        """
        Computes an intuitive safety score (0 - 100) based on weather metrics and triggered SOPs.
        100 = Ideal, 0 = Extreme Danger.
        """
        score = 100

        # Penalize for SOP severities
        for match in matched_sops:
            sev = match.sop.severity
            if sev == "CRITICAL":
                score -= 60
            elif sev == "HIGH":
                score -= 35
            elif sev == "MEDIUM":
                score -= 20
            elif sev == "LOW":
                score -= 10
            elif sev == "ADVISORY":
                score -= 5

        # Penalize for extreme temperatures
        if weather.temperature >= 38:
            score -= 25
        elif weather.temperature >= 32:
            score -= 10
        elif weather.temperature <= -5:
            score -= 25
        elif weather.temperature <= 5:
            score -= 10

        # Penalize for high wind
        if weather.wind_speed >= 45:
            score -= 30
        elif weather.wind_speed >= 30:
            score -= 15

        # Penalize for rain / thunderstorms
        if weather.lightning_risk:
            score -= 50
        elif weather.precipitation >= 10:
            score -= 30
        elif weather.precipitation > 0.5:
            score -= 10

        # Penalize for high UV
        if weather.uv_index >= 9:
            score -= 15
        elif weather.uv_index >= 6:
            score -= 8

        # Clamp between 0 and 100
        return max(0, min(100, score))

    def get_gear_checklist(self, weather: WeatherData, activity: str, matched_sops: List[SOPMatchResult]) -> List[str]:
        """Generates dynamic gear and preparation checklist based on current conditions."""
        gear = []
        act = (activity or "general outdoor").lower()

        # UV protection
        if weather.uv_index >= 5.0:
            gear.append("🧴 SPF 30+ / 50+ Broad-Spectrum Sunscreen")
            gear.append("🕶️ UV-400 Polarized Sunglasses")
            gear.append("🧢 Wide-brim hat or sun visor")

        # Heat / Hydration
        if weather.temperature >= 28.0:
            gear.append("💧 Minimum 1.5L - 2L Water with Electrolyte Tablets")
            gear.append("👕 Lightweight, breathable, moisture-wicking apparel")

        # Cold / Wind protection
        if weather.temperature <= 10.0:
            gear.append("🧤 Thermal windproof gloves & neck gaiter")
            gear.append("🧥 Multi-layer moisture-wicking fleece & thermal base")
        if weather.wind_speed >= 25.0:
            gear.append("🧥 Windbreaker / windproof outer shell jacket")

        # Rain / Wet weather
        if weather.precipitation > 0.1 or weather.precipitation_probability >= 40:
            gear.append("☔ Packable waterproof rain jacket or poncho")
            gear.append("🎒 Waterproof dry-bag / rain cover for gear")

        # Activity-specific gear
        if "cycl" in act or "bike" in act:
            gear.append("⛑️ High-visibility certified cycling helmet")
            gear.append("💡 Front white and rear flashing red LED safety lights")
        elif "run" in act or "jog" in act:
            gear.append("👟 Cushioned running shoes with anti-slip tread")
        elif "hike" in act or "trek" in act:
            gear.append("🥾 Ankle-support trail boots & trekking poles")
            gear.append("🗺️ Offline GPS trail map / physical compass & whistle")
        elif "drone" in act or "uav" in act:
            gear.append("🚁 Propeller guards & spare battery thermal warming pouch")
            gear.append("📱 Calibrated anemometer for ground wind checking")
        elif "swim" in act or "water" in act:
            gear.append("🦺 Certified buoyancy aid / PFD life vest")
            gear.append("🏊 Highly visible tow float / safety buoy")

        return gear if gear else ["👟 Standard comfortable outdoor footwear", "💧 Water bottle", "📱 Charged mobile phone"]

    def generate_advisory(
        self,
        query: str,
        intent: IntentExtraction,
        weather: WeatherData,
        matched_sops: List[SOPMatchResult],
    ) -> Dict[str, Any]:
        """
        Synthesizes the final advisory response combining deterministic SOP enforcement
        with clear, structured natural language guidance.
        """
        # 1. Handle Adversarial Prompt Injections
        if intent.adversarial_attempt:
            return {
                "summary": "⚠️ Safety Policy Enforcement Notice",
                "risk_level": "RESTRICTED",
                "risk_color": "#ef4444",
                "safety_score": 0,
                "advisory_markdown": (
                    "### 🛡️ Safety Verification Alert\n\n"
                    "The system detected an attempt to override standard operating safety guidelines or safety policies. "
                    "Weather safety thresholds and Standard Operating Procedures (SOPs) are strict and immutable. "
                    f"Current conditions in **{weather.location_name}** are: Temperature {weather.temperature}°C, "
                    f"Wind {weather.wind_speed} km/h, Weather: {weather.weather_description}."
                ),
                "matched_sops": [],
                "gear_checklist": [],
                "activity_status": "PROHIBITED_OVERRIDE",
            }

        safety_score = self.calculate_safety_score(weather, matched_sops)
        gear = self.get_gear_checklist(weather, intent.activity or "general outdoor", matched_sops)

        # Determine overall risk status
        if matched_sops:
            highest_sev = matched_sops[0].sop.severity
            if highest_sev == "CRITICAL":
                risk_level = "CRITICAL HAZARD"
                risk_color = "#ef4444"
                activity_status = "NOT RECOMMENDED / CANCEL"
            elif highest_sev == "HIGH":
                risk_level = "HIGH RISK"
                risk_color = "#f97316"
                activity_status = "RESTRICTED / POSTPONE"
            elif highest_sev == "MEDIUM":
                risk_level = "MODERATE CAUTION"
                risk_color = "#eab308"
                activity_status = "PROCEED WITH PRECAUTION"
            else:
                risk_level = "LOW ADVISORY"
                risk_color = "#3b82f6"
                activity_status = "SAFE WITH AWARENESS"
        else:
            risk_level = "FAVORABLE"
            risk_color = "#10b981"
            activity_status = "OPTIMAL FOR ACTIVITY"

        # Build clean Markdown advisory
        lines = []
        activity_title = (intent.activity or "Outdoor Activity").title()
        lines.append(f"## 🌤️ Weather Advisory for **{activity_title}** in **{weather.location_name}**\n")

        # Weather snapshot row
        lines.append(
            f"**Current Atmosphere:** {weather.weather_description} | "
            f"🌡️ **{weather.temperature}°C** (Feels like {weather.apparent_temperature}°C) | "
            f"💨 Wind **{weather.wind_speed} km/h** (Gusts {weather.wind_gusts} km/h) | "
            f"💧 Humidity **{weather.relative_humidity}%** | "
            f"☀️ UV Index **{weather.uv_index}**\n"
        )

        # Triggered SOP Alert Boxes
        if matched_sops:
            lines.append("### 🚨 Active Standard Operating Procedures (SOPs) Triggered:\n")
            for r in matched_sops:
                badge_emoji = "🛑" if r.sop.severity == "CRITICAL" else "⚠️" if r.sop.severity == "HIGH" else "ℹ️"
                lines.append(f"> {badge_emoji} **[{r.sop.id}] {r.sop.name}** (`{r.sop.severity}` Severity)")
                lines.append(f"> **Condition Triggered:** {r.reason}")
                lines.append(f"> **Mandatory Directive:** {r.sop.advisory}")
                lines.append(f"> **Required Action:** **{r.sop.recommended_action}**\n")
        else:
            lines.append("✅ **No Adverse Weather SOPs Triggered.** Atmospheric conditions are within nominal safety thresholds for this activity.\n")

        # Demographic Notes if applicable
        if intent.vulnerable_groups:
            groups_str = ", ".join([g.title() for g in intent.vulnerable_groups])
            lines.append(f"### 👥 Vulnerable Demographic Guidance ({groups_str})\n")
            if weather.temperature >= 32.0 or weather.uv_index >= 6.0:
                lines.append("- Ensure frequent shaded rests, high hydration intervals, and continuous sun protection.")
            elif weather.temperature <= 10.0:
                lines.append("- Ensure extra insulation layers, protect extremities against wind chill, and limit prolonged exposure.")
            else:
                lines.append("- Conditions are comfortable; ensure regular water intake and sun awareness.")
            lines.append("")

        # Actionable Recommendations
        lines.append("### 📋 Expert Recommendations & Precautions\n")
        if activity_status.startswith("NOT") or activity_status.startswith("RESTRICTED"):
            lines.append(f"1. **Safety First:** We strongly advise rescheduling or moving `{activity_title}` indoors.")
            lines.append("2. **Monitor Telemetry:** Check updated radar before planning subsequent outings.")
            lines.append("3. **Emergency Readiness:** Maintain access to shelter and reliable communication.")
        else:
            lines.append(f"1. **Execution Window:** Current weather is suitable for `{activity_title}`.")
            lines.append("2. **Hydration & Protection:** Maintain hydration and follow the gear checklist.")
            lines.append("3. **Awareness:** Stay observant of shifting cloud formations or sudden wind gust increases.")

        markdown_text = "\n".join(lines)

        return {
            "summary": f"{activity_status} for {activity_title} in {weather.location_name}",
            "risk_level": risk_level,
            "risk_color": risk_color,
            "safety_score": safety_score,
            "activity_status": activity_status,
            "advisory_markdown": markdown_text,
            "matched_sops": [
                {
                    "id": m.sop.id,
                    "name": m.sop.name,
                    "severity": m.sop.severity,
                    "priority": m.sop.priority,
                    "advisory": m.sop.advisory,
                    "action": m.sop.recommended_action,
                    "matched_reasons": m.matched_conditions,
                }
                for m in matched_sops
            ],
            "gear_checklist": gear,
        }

llm_service = LLMService()
