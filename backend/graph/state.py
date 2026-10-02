from typing import TypedDict, List, Dict, Any, Optional

class AdvisorState(TypedDict, total=False):
    session_id: str
    user_query: str
    conversation_history: List[Dict[str, str]]
    intent: Optional[Dict[str, Any]]
    location: Optional[str]
    location_resolved: bool
    latitude: Optional[float]
    longitude: Optional[float]
    weather: Optional[Dict[str, Any]]
    raw_weather: Optional[Dict[str, Any]]
    weather_available: bool
    matched_sops: List[Dict[str, Any]]
    selected_sop: Optional[Dict[str, Any]]
    sop_found: bool
    conflict_resolution: Optional[str]
    adversarial_attempt: bool
    error: Optional[str]
    final_response: str
