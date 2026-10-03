import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.config import settings
from backend.graph.agent import advisor_graph
from backend.sop.engine import SOPEngine
from backend.sop.models import WeatherData
from backend.services.weather_service import weather_service


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Weather-Advisory Support Bot with LangGraph and SOP Engine",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sop_engine = SOPEngine()


# ============================================================
# REQUEST MODELS
# ============================================================

class AdvisorChatRequest(BaseModel):
    session_id: str = Field(
        default="default-session",
        description="Conversation session identifier",
    )

    message: str = Field(
        ...,
        description="User's natural-language message",
    )

    location: Optional[str] = Field(
        default=None,
        description="Optional explicit location override",
    )

    activity: Optional[str] = Field(
        default=None,
        description="Optional activity override",
    )

    vulnerable_groups: Optional[List[str]] = Field(
        default_factory=list,
        description="Optional vulnerable groups",
    )


class WeatherLookupRequest(BaseModel):
    location: str


class SOPSimulationRequest(BaseModel):
    activity: str = "cycling"
    target_groups: List[str] = Field(default_factory=list)

    temperature: float = 25.0
    apparent_temperature: Optional[float] = None

    wind_speed: float = 15.0
    wind_gusts: float = 20.0
    wind_chill: Optional[float] = None

    precipitation: float = 0.0
    precipitation_probability: float = 10.0

    visibility: float = 10.0
    uv_index: float = 3.0

    weather_code: int = 0
    lightning_risk: bool = False
    wave_height: Optional[float] = None


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "sops_loaded": len(sop_engine.get_all_sops()),
        "langgraph": True,
    }


# ============================================================
# SOP ENDPOINT
# ============================================================

@app.get("/api/sops")
async def get_all_sops():

    sops = sop_engine.get_all_sops()

    return {
        "total": len(sops),
        "sops": [s.model_dump() for s in sops],
    }


# ============================================================
# ACTIVITIES
# ============================================================

@app.get("/api/activities")
async def get_activities():

    return {
        "activities": [
            {
                "id": "cycling",
                "name": "Cycling & Micromobility",
                "icon": "🚴",
                "category": "mobility",
            },
            {
                "id": "running",
                "name": "Running & Jogging",
                "icon": "🏃",
                "category": "cardio",
            },
            {
                "id": "hiking",
                "name": "Hiking & Mountain Trails",
                "icon": "🥾",
                "category": "adventure",
            },
            {
                "id": "swimming",
                "name": "Open Water Swimming & Watersports",
                "icon": "🏊",
                "category": "water",
            },
            {
                "id": "walking",
                "name": "Walking & Daily Commute",
                "icon": "🚶",
                "category": "daily",
            },
            {
                "id": "general outdoor",
                "name": "General Outdoor & Parks",
                "icon": "🌳",
                "category": "leisure",
            },
        ],
        "target_groups": [
            {
                "id": "general",
                "name": "General Adults",
                "icon": "👤",
            },
            {
                "id": "children",
                "name": "Children & Toddlers",
                "icon": "👶",
            },
            {
                "id": "elderly",
                "name": "Elderly / Seniors",
                "icon": "👵",
            },
            {
                "id": "pregnant",
                "name": "Pregnant Women",
                "icon": "🤰",
            },
            {
                "id": "chronic_illness",
                "name": "Asthma / Respiratory Sensitivity",
                "icon": "🫁",
            },
        ],
    }


# ============================================================
# WEATHER LOOKUP
# ============================================================

@app.post("/api/weather/lookup")
async def lookup_weather(req: WeatherLookupRequest):

    geo = await weather_service.geocode(req.location)

    if not geo:
        raise HTTPException(
            status_code=404,
            detail=f"Location '{req.location}' could not be resolved.",
        )

    weather_obj, raw_data = await weather_service.get_weather(
        latitude=geo["latitude"],
        longitude=geo["longitude"],
        location_name=geo["name"],
        timezone=geo.get("timezone", "auto"),
    )

    return {
        "location": geo,
        "weather": weather_obj.model_dump(
            exclude={"raw_response"}
        ),
        "hourly": raw_data.get("hourly", {}),
        "daily": raw_data.get("daily", {}),
    }


# ============================================================
# LANGGRAPH CHAT
# ============================================================

@app.post("/api/advisor/chat")
async def chat_advisor(req: AdvisorChatRequest):

    try:

        # ----------------------------------------------------
        # IMPORTANT:
        # Do NOT call advisor_service.get_advice_for_query()
        # here.
        #
        # The request must enter the LangGraph StateGraph.
        # ----------------------------------------------------

        initial_state = {
            "session_id": req.session_id,

            "user_query": req.message,

            # Explicit frontend override.
            "location": req.location,

            # Only use activity when explicitly supplied.
            # Otherwise LangGraph intent detection handles it.
            "activity": req.activity,

            "vulnerable_groups": req.vulnerable_groups or [],

            "intent": None,

            "location_resolved": False,

            "latitude": None,
            "longitude": None,

            "weather": None,
            "weather_available": False,

            "matched_sops": [],
            "selected_sop": None,
            "sop_found": False,

            "conflict_resolution": None,

            "adversarial_attempt": False,

            "error": None,

            "final_response": None,
        }

        result = await advisor_graph.ainvoke(initial_state)

        return {
            "session_id": req.session_id,

            "response": result.get(
                "final_response",
                "I could not generate a response."
            ),

            "intent": result.get("intent"),

            "location": result.get("location"),

            "weather": result.get("weather"),

            "matched_sops": result.get(
                "matched_sops",
                []
            ),

            "selected_sop": result.get(
                "selected_sop"
            ),

            "sop_found": result.get(
                "sop_found",
                False
            ),

            "conflict_resolution": result.get(
                "conflict_resolution"
            ),

            "error": result.get("error"),

        }

    except Exception as exc:

        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# SOP SIMULATOR
# ============================================================

@app.post("/api/sop/simulate")
async def simulate_sop_rules(
    req: SOPSimulationRequest
):

    sim_weather = WeatherData(
        location_name="Simulation Environment",

        latitude=0.0,
        longitude=0.0,
        timezone="UTC",

        temperature=req.temperature,

        apparent_temperature=(
            req.apparent_temperature
            if req.apparent_temperature is not None
            else req.temperature
        ),

        wind_speed=req.wind_speed,
        wind_gusts=req.wind_gusts,

        wind_chill=(
            req.wind_chill
            if req.wind_chill is not None
            else req.temperature
        ),

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


# ============================================================
# FRONTEND
# ============================================================

FRONTEND_DIR = (
    Path(__file__).resolve().parent.parent
    / "frontend"
)

if FRONTEND_DIR.exists():

    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIR),
        name="static",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):

        file_path = FRONTEND_DIR / full_path

        if file_path.is_file():
            return FileResponse(file_path)

        return FileResponse(
            FRONTEND_DIR / "index.html"
        )