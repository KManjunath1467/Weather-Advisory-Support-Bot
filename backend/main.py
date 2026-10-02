import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.config import settings
from backend.services.weather_service import weather_service
from backend.services.advisor_service import advisor_service
from backend.sop.engine import SOPEngine
from backend.sop.models import WeatherData, ConditionRule

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Weather-Advisory Support Bot with LangGraph StateGraph & Deterministic SOP Engine",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sop_engine = SOPEngine()

# Request Models
class AdvisorChatRequest(BaseModel):
    session_id: Optional[str] = Field("default", description="Client session ID for conversation memory")
    message: Optional[str] = Field(None, description="User message/query, e.g. 'Can I go cycling in Bengaluru?'")
    query: Optional[str] = Field(None, description="Alias for message")
    location: Optional[str] = Field(None, description="Optional city or location override")
    activity: Optional[str] = Field(None, description="Optional activity override")
    vulnerable_groups: Optional[List[str]] = Field(default_factory=list, description="Optional target groups")

class WeatherLookupRequest(BaseModel):
    location: str = Field(..., description="City name or address to query")

class SOPSimulationRequest(BaseModel):
    activity: str = Field("cycling", description="Outdoor activity to evaluate")
    target_groups: List[str] = Field(default_factory=list)
    temperature: float = Field(25.0)
    apparent_temperature: Optional[float] = None
    wind_speed: float = Field(15.0)
    wind_gusts: float = Field(20.0)
    wind_chill: Optional[float] = None
    precipitation: float = Field(0.0)
    precipitation_probability: float = Field(10.0)
    visibility: float = Field(10.0)
    uv_index: float = Field(3.0)
    weather_code: int = Field(0)
    lightning_risk: bool = Field(False)
    wave_height: Optional[float] = None

# API Endpoints
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "langgraph_agent": "active",
        "sops_loaded": len(sop_engine.get_all_sops()),
    }

@app.get("/api/sops")
async def get_all_sops():
    """Returns all loaded Standard Operating Procedures with rules and directives."""
    sops = sop_engine.get_all_sops()
    return {
        "total": len(sops),
        "sops": [s.model_dump() for s in sops],
    }

@app.get("/api/activities")
async def get_activities():
    """Returns supported outdoor activity groups and target demographics."""
    return {
        "activities": [
            {"id": "cycling", "name": "Cycling & Micromobility", "icon": "🚴", "category": "mobility"},
            {"id": "running", "name": "Running & Jogging", "icon": "🏃", "category": "cardio"},
            {"id": "hiking", "name": "Hiking & Mountain Trails", "icon": "🥾", "category": "adventure"},
            {"id": "swimming", "name": "Open Water Swimming & Watersports", "icon": "🏊", "category": "water"},
            {"id": "drone flying", "name": "Drone & UAV Flight", "icon": "🚁", "category": "aviation"},
            {"id": "picnic", "name": "Family Picnic & Outings", "icon": "🧺", "category": "family_recreation"},
            {"id": "outdoor sports", "name": "Outdoor Sports (Football/Cricket/Golf)", "icon": "⚽", "category": "sports"},
            {"id": "walking", "name": "Walking & Daily Commute", "icon": "🚶", "category": "daily"},
            {"id": "general outdoor", "name": "General Outdoor & Parks", "icon": "🌳", "category": "leisure"},
        ],
        "target_groups": [
            {"id": "general", "name": "General Adults", "icon": "👤"},
            {"id": "children", "name": "Children & Toddlers", "icon": "👶"},
            {"id": "elderly", "name": "Elderly / Seniors", "icon": "👵"},
            {"id": "pregnant", "name": "Pregnant Women", "icon": "🤰"},
            {"id": "chronic_illness", "name": "Asthma / Respiratory Sensitivity", "icon": "🫁"},
        ],
    }

@app.post("/api/weather/lookup")
async def lookup_weather(req: WeatherLookupRequest):
    """Fetches real-time weather and forecast for any city or location."""
    geo = await weather_service.geocode(req.location)
    if not geo:
        raise HTTPException(status_code=404, detail=f"Location '{req.location}' could not be resolved.")
    
    weather_obj, raw_data = await weather_service.get_weather(
        latitude=geo["latitude"],
        longitude=geo["longitude"],
        location_name=geo["name"],
        timezone=geo.get("timezone", "auto"),
    )
    
    if not weather_obj:
        raise HTTPException(status_code=503, detail="Live weather service temporarily unavailable.")

    return {
        "location": geo,
        "weather": weather_obj.model_dump(exclude={"raw_response"}),
        "hourly": raw_data.get("hourly", {}) if raw_data else {},
        "daily": raw_data.get("daily", {}) if raw_data else {},
    }

@app.post("/api/advisor/chat")
async def chat_advisor(req: AdvisorChatRequest):
    """
    Processes user query strictly using the LangGraph StateGraph agent.
    Maintains session-level conversation memory.
    """
    user_msg = req.message or req.query
    if not user_msg:
        raise HTTPException(status_code=400, detail="Missing message or query parameter.")

    try:
        res = await advisor_service.process_chat(
            query=user_msg,
            session_id=req.session_id or "default",
            location=req.location,
            activity=req.activity,
            vulnerable_groups=req.vulnerable_groups,
        )
        return res
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sop/simulate")
async def simulate_sop_rules(req: SOPSimulationRequest):
    """
    Live simulator allowing users and administrators to test arbitrary weather parameter
    combinations and see which SOP rules fire instantly with matched reasons.
    """
    sim_weather = WeatherData(
        location_name="Simulation Environment",
        latitude=0.0,
        longitude=0.0,
        timezone="UTC",
        temperature=req.temperature,
        apparent_temperature=req.apparent_temperature or req.temperature,
        wind_speed=req.wind_speed,
        wind_gusts=req.wind_gusts,
        wind_chill=req.wind_chill or req.temperature,
        relative_humidity=50.0,
        precipitation=req.precipitation,
        precipitation_probability=req.precipitation_probability,
        weather_code=req.weather_code,
        weather_description="Simulated Weather",
        visibility=req.visibility,
        uv_index=req.uv_index,
        is_day=True,
        lightning_risk=req.lightning_risk,
        wave_height=req.wave_height,
        raw_response={},
    )

    matched = sop_engine.evaluate(
        weather=sim_weather,
        activity=req.activity,
        target_groups=req.target_groups,
    )

    return {
        "activity": req.activity,
        "target_groups": req.target_groups,
        "matched_count": len(matched),
        "matched_sops": [
            {
                "id": m.sop.id,
                "name": m.sop.name,
                "category": m.sop.category,
                "severity": m.sop.severity,
                "priority": m.sop.priority,
                "advisory": m.sop.advisory,
                "action": m.sop.recommended_action,
                "reasons": m.matched_conditions,
            }
            for m in matched
        ],
    }

# Mount static frontend files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
