import yaml
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from backend.sop.models import SOPDefinition, ConditionRule, SOPMatchResult, WeatherData, SeverityLevel
from backend.config import settings

SEVERITY_WEIGHTS: Dict[SeverityLevel, int] = {
    "CRITICAL": 1000,
    "HIGH": 700,
    "MEDIUM": 400,
    "LOW": 200,
    "ADVISORY": 100,
}

class SOPEngine:
    """
    Deterministic Standard Operating Procedure (SOP) Rule Engine.
    Loads SOPs from YAML and evaluates weather conditions against activity requirements.
    """

    def __init__(self, sops_file_path: Optional[Path] = None):
        self.sops_file_path = sops_file_path or settings.sop_file_path
        self.sops: List[SOPDefinition] = []
        self.load_sops()

    def load_sops(self) -> None:
        """Loads and parses the SOP configuration file."""
        if not self.sops_file_path.exists():
            raise FileNotFoundError(f"SOP definition file not found at: {self.sops_file_path}")

        with open(self.sops_file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        raw_sops = data.get("sops", [])
        self.sops = [SOPDefinition(**sop_dict) for sop_dict in raw_sops]
        # Sort SOPs by priority descending
        self.sops.sort(key=lambda s: (s.priority, SEVERITY_WEIGHTS.get(s.severity, 0)), reverse=True)

    def get_all_sops(self) -> List[SOPDefinition]:
        return self.sops

    def get_sop_by_id(self, sop_id: str) -> Optional[SOPDefinition]:
        for sop in self.sops:
            if sop.id.lower() == sop_id.lower():
                return sop
        return None

    def evaluate_condition(self, rule: ConditionRule, weather: WeatherData) -> Tuple[bool, List[str]]:
        """
        Recursively evaluates a ConditionRule against current WeatherData.
        Returns (is_matched, list_of_reasons).
        """
        reasons: List[str] = []

        # 1. Handle all_of logic
        if rule.all_of:
            all_matched = True
            sub_reasons = []
            for sub_rule in rule.all_of:
                matched, sub_r = self.evaluate_condition(sub_rule, weather)
                if not matched:
                    all_matched = False
                    break
                sub_reasons.extend(sub_r)
            if all_matched:
                reasons.extend(sub_reasons)
            else:
                return False, []

        # 2. Handle any_of logic
        if rule.any_of:
            any_matched = False
            sub_reasons = []
            for sub_rule in rule.any_of:
                matched, sub_r = self.evaluate_condition(sub_rule, weather)
                if matched:
                    any_matched = True
                    sub_reasons.extend(sub_r)
            if any_matched:
                reasons.extend(sub_reasons)
            else:
                return False, []

        # 3. Direct condition checks
        if rule.temperature_gte is not None:
            if weather.temperature >= rule.temperature_gte:
                reasons.append(f"Temperature ({weather.temperature}°C) >= {rule.temperature_gte}°C")
            else:
                return False, []

        if rule.temperature_lte is not None:
            if weather.temperature <= rule.temperature_lte:
                reasons.append(f"Temperature ({weather.temperature}°C) <= {rule.temperature_lte}°C")
            else:
                return False, []

        if rule.wind_speed_gte is not None:
            if weather.wind_speed >= rule.wind_speed_gte:
                reasons.append(f"Wind speed ({weather.wind_speed} km/h) >= {rule.wind_speed_gte} km/h")
            else:
                return False, []

        if rule.wind_speed_lte is not None:
            if weather.wind_speed <= rule.wind_speed_lte:
                reasons.append(f"Wind speed ({weather.wind_speed} km/h) <= {rule.wind_speed_lte} km/h")
            else:
                return False, []

        if rule.wind_gusts_gte is not None:
            if weather.wind_gusts >= rule.wind_gusts_gte:
                reasons.append(f"Wind gusts ({weather.wind_gusts} km/h) >= {rule.wind_gusts_gte} km/h")
            else:
                return False, []

        if rule.wind_chill_lte is not None:
            wind_chill_val = weather.wind_chill if weather.wind_chill is not None else weather.temperature
            if wind_chill_val <= rule.wind_chill_lte:
                reasons.append(f"Wind chill ({wind_chill_val}°C) <= {rule.wind_chill_lte}°C")
            else:
                return False, []

        if rule.precipitation_gte is not None:
            if weather.precipitation >= rule.precipitation_gte:
                reasons.append(f"Precipitation ({weather.precipitation} mm) >= {rule.precipitation_gte} mm")
            else:
                return False, []

        if rule.precipitation_probability_gte is not None:
            if weather.precipitation_probability >= rule.precipitation_probability_gte:
                reasons.append(f"Precipitation probability ({weather.precipitation_probability}%) >= {rule.precipitation_probability_gte}%")
            else:
                return False, []

        if rule.visibility_lte is not None:
            if weather.visibility <= rule.visibility_lte:
                reasons.append(f"Visibility ({weather.visibility} km) <= {rule.visibility_lte} km")
            else:
                return False, []

        if rule.uv_index_gte is not None:
            if weather.uv_index >= rule.uv_index_gte:
                reasons.append(f"UV Index ({weather.uv_index}) >= {rule.uv_index_gte}")
            else:
                return False, []

        if rule.wave_height_gte is not None:
            wave_h = weather.wave_height or 0.0
            if wave_h >= rule.wave_height_gte:
                reasons.append(f"Wave height ({wave_h} m) >= {rule.wave_height_gte} m")
            else:
                return False, []

        if rule.lightning_risk is not None:
            if weather.lightning_risk == rule.lightning_risk:
                reasons.append(f"Lightning risk is {rule.lightning_risk}")
            else:
                return False, []

        if rule.weather_code_in is not None:
            if weather.weather_code in rule.weather_code_in:
                reasons.append(f"Weather code ({weather.weather_code}: {weather.weather_description}) matches rule codes {rule.weather_code_in}")
            else:
                return False, []

        return True, reasons

    def match_activity(self, sop: SOPDefinition, activity: Optional[str]) -> bool:
        """Determines whether an activity matches the SOP scope."""
        if not activity:
            return "general outdoor" in [a.lower() for a in sop.activities] or not sop.activities

        act_lower = activity.strip().lower()
        sop_acts = [a.lower() for a in sop.activities]

        if act_lower in sop_acts:
            return True
        for sa in sop_acts:
            if sa in act_lower or act_lower in sa:
                return True
        return False

    def match_target_groups(self, sop: SOPDefinition, target_groups: List[str]) -> bool:
        """Determines whether any user target demographic matches the SOP."""
        if not sop.target_groups:
            return True
        if not target_groups:
            return False
        user_groups = [g.lower() for g in target_groups]
        for tg in sop.target_groups:
            if tg.lower() in user_groups or any(g in tg.lower() for g in user_groups):
                return True
        return False

    def evaluate(
        self,
        weather: WeatherData,
        activity: Optional[str] = None,
        target_groups: Optional[List[str]] = None,
    ) -> List[SOPMatchResult]:
        """
        Evaluates all loaded SOPs against given weather, activity, and target groups.
        Returns matched SOPs sorted by priority and severity.
        """
        results: List[SOPMatchResult] = []
        target_groups = target_groups or []

        for sop in self.sops:
            # 1. Activity scope check
            act_match = self.match_activity(sop, activity)
            # 2. Target group scope check
            group_match = self.match_target_groups(sop, target_groups) if sop.target_groups else True

            if not act_match and not (sop.target_groups and group_match):
                continue

            # 3. Weather conditions evaluation
            matched, reasons = self.evaluate_condition(sop.conditions, weather)
            if matched:
                results.append(
                    SOPMatchResult(
                        sop=sop,
                        matched=True,
                        matched_conditions=reasons,
                        reason="; ".join(reasons)
                    )
                )

        results.sort(
            key=lambda r: (
                r.sop.priority,
                SEVERITY_WEIGHTS.get(r.sop.severity, 0)
            ),
            reverse=True,
        )
        return results
