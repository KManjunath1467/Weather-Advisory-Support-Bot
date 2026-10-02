from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

SeverityLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "ADVISORY"]

class ConditionRule(BaseModel):
    temperature_gte: Optional[float] = None
    temperature_lte: Optional[float] = None
    wind_speed_gte: Optional[float] = None
    wind_speed_lte: Optional[float] = None
    wind_gusts_gte: Optional[float] = None
    wind_chill_lte: Optional[float] = None
    precipitation_gte: Optional[float] = None
    precipitation_probability_gte: Optional[float] = None
    visibility_lte: Optional[float] = None
    uv_index_gte: Optional[float] = None
    wave_height_gte: Optional[float] = None
    lightning_risk: Optional[bool] = None
    weather_code_in: Optional[List[int]] = None
    all_of: Optional[List["ConditionRule"]] = None
    any_of: Optional[List["ConditionRule"]] = None

class SOPDefinition(BaseModel):
    id: str = Field(..., description="Unique SOP ID, e.g., SOP-01")
    name: str = Field(..., description="Human-readable title of SOP")
    category: str = Field(..., description="Category group")
    activities: List[str] = Field(default_factory=list, description="Activities covered by this SOP")
    target_groups: List[str] = Field(default_factory=list, description="Target demographic groups (e.g., elderly, children)")
    severity: SeverityLevel = Field(..., description="Severity level")
    priority: int = Field(default=50, description="Deterministic priority score for conflict resolution")
    conditions: ConditionRule = Field(..., description="Weather condition rules that trigger this SOP")
    advisory: str = Field(..., description="Mandatory core advisory text from the SOP")
    recommended_action: str = Field(..., description="Recommended action specified in the SOP")

class SOPMatchResult(BaseModel):
    sop: SOPDefinition
    matched: bool
    matched_conditions: List[str] = Field(default_factory=list)
    reason: str = ""

class IntentExtraction(BaseModel):
    activity: Optional[str] = Field(None, description="The primary outdoor activity extracted (e.g. cycling, running, hiking, swimming, drone flying)")
    location: Optional[str] = Field(None, description="The geographical city/region/location mentioned")
    time_reference: Optional[str] = Field(None, description="Time reference (e.g., today, this afternoon, tomorrow)")
    vulnerable_groups: List[str] = Field(default_factory=list, description="Vulnerable demographics mentioned (e.g., elderly, children, pregnant, asthma)")
    travel_context: Optional[str] = Field(None, description="Context such as commuting, tourism, race, recreation")
    adversarial_attempt: bool = Field(False, description="Whether the user is attempting prompt-injection, policy override, or jailbreaking")
    clarification_needed: bool = Field(False, description="Whether essential details (like activity or location) are missing")

class WeatherData(BaseModel):
    location_name: str
    latitude: float
    longitude: float
    timezone: str = "UTC"
    temperature: float
    apparent_temperature: float
    wind_speed: float
    wind_gusts: float
    wind_chill: Optional[float] = None
    relative_humidity: float
    precipitation: float
    precipitation_probability: float
    weather_code: int
    weather_description: str
    visibility: float # in km
    uv_index: float
    is_day: bool = True
    lightning_risk: bool = False
    wave_height: Optional[float] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict)
