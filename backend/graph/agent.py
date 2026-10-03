from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, START, END

from backend.graph.state import AdvisorState
from backend.services.intent_service import intent_service
from backend.services.weather_service import weather_service
from backend.sop.engine import SOPEngine
from backend.sop.models import WeatherData
from backend.memory.session_store import session_store

sop_engine = SOPEngine()

SEVERITY_WEIGHTS = {
    "CRITICAL": 1000,
    "HIGH": 700,
    "MEDIUM": 400,
    "LOW": 200,
    "ADVISORY": 100,
}

# ----------------- GRAPH NODES -----------------

async def understand_question_node(state: AdvisorState) -> Dict[str, Any]:
    """Extracts activity, location, demographic groups, and detects adversarial prompt injections."""
    query = state.get("user_query", "")
    session_id = state.get("session_id", "default")
    session = session_store.get_or_create(session_id)

    initial_loc = state.get("location") or session.location

    # Extract intent from text
    intent = intent_service.extract_intent(query, default_location=initial_loc)
    
    # Respect an explicitly supplied activity first.
    explicit_activity = state.get("activity")
    if explicit_activity:
        intent.activity = explicit_activity
        session_store.update(session_id, activity=explicit_activity)
    elif intent.activity:
        # A newly detected activity becomes the active activity for
        # subsequent advisory questions in this session.
        session_store.update(session_id, activity=intent.activity)
    elif session.activity:
        # Do not silently carry an old activity into an explicit
        # weather-only request. This is important for queries such as
        # "What is the weather in Bengaluru?" after a cycling advisory.
        weather_only_markers = (
            "weather", "temperature", "forecast", "wind", "rain",
            "precipitation", "humidity", "uv index", "uv",
            "how hot", "how cold", "weather like"
        )
        is_weather_only = any(
            marker in query.lower() for marker in weather_only_markers
        ) and not intent.activity

        if not is_weather_only:
            intent.activity = session.activity

    if intent.vulnerable_groups:
        session_store.update(session_id, vulnerable_groups=intent.vulnerable_groups)
    elif session.vulnerable_groups:
        intent.vulnerable_groups = session.vulnerable_groups

    final_loc = intent.location or initial_loc

    # Defensive guard: an activity must never be interpreted as a location.
    # Example: "Can I go for cycling?" must resolve cycling as the activity
    # and reuse the previous/session location.
    if (
        intent.activity
        and final_loc
        and final_loc.strip().lower() == intent.activity.strip().lower()
    ):
        final_loc = initial_loc

    return {
        "intent": intent.model_dump(),
        "adversarial_attempt": intent.adversarial_attempt,
        "location": final_loc,
    }

async def adversarial_error_node(state: AdvisorState) -> Dict[str, Any]:
    """Handles adversarial jailbreak or safety override attempts."""
    return {
        "error": "adversarial_override_attempt",
        "final_response": (
            "Safety Policy Enforcement Notice:\n\n"
            "The system detected an attempt to override standard operating safety guidelines or bypass SOP safety rules. "
            "Weather safety thresholds and Standard Operating Procedures (SOPs) are strict, authoritative, and immutable. "
            "Safety policies cannot be overridden."
        ),
    }

async def resolve_location_node(state: AdvisorState) -> Dict[str, Any]:
    """Resolves geographical coordinates strictly via Open-Meteo Geocoding without fake fallbacks."""
    # If already resolved (e.g. in test state), keep it
    if state.get("location_resolved") and state.get("latitude") is not None:
        return {
            "location": state.get("location"),
            "latitude": state.get("latitude"),
            "longitude": state.get("longitude"),
            "location_resolved": True,
        }

    session_id = state.get("session_id", "default")
    session = session_store.get_or_create(session_id)
    
    loc_query = state.get("location") or session.location
    if not loc_query:
        return {"location_resolved": False, "location": None}

    geo = await weather_service.geocode(loc_query)
    if geo:
        session_store.update(
            session_id,
            location=geo["name"],
            latitude=geo["latitude"],
            longitude=geo["longitude"],
        )
        return {
            "location": geo["name"],
            "latitude": geo["latitude"],
            "longitude": geo["longitude"],
            "location_resolved": True,
        }

    return {"location_resolved": False, "location": loc_query}

async def location_error_node(state: AdvisorState) -> Dict[str, Any]:
    """Handles unresolvable locations honestly without inventing coordinates."""
    attempted_loc = state.get("location") or "the specified location"
    return {
        "error": "location_unresolved",
        "final_response": f"I couldn't resolve the location '{attempted_loc}', so I can't retrieve live weather for it. Please provide a city or location I can resolve.",
    }

async def fetch_weather_node(state: AdvisorState) -> Dict[str, Any]:
    """Fetches real-time weather from Open-Meteo with exact coordinates."""
    # If weather was already provided (e.g. in test or simulation state), preserve it
    if state.get("weather") is not None and state.get("weather_available"):
        return {
            "weather": state["weather"],
            "raw_weather": state.get("raw_weather"),
            "weather_available": True,
        }

    lat = state.get("latitude")
    lon = state.get("longitude")
    loc_name = state.get("location") or "Unknown"

    if lat is None or lon is None:
        return {"weather_available": False, "weather": None, "raw_weather": None}

    weather_obj, raw_data = await weather_service.get_weather(
        latitude=lat, longitude=lon, location_name=loc_name
    )

    if weather_obj is not None:
        return {
            "weather": weather_obj.model_dump(exclude={"raw_response"}),
            "raw_weather": raw_data,
            "weather_available": True,
        }

    return {"weather_available": False, "weather": None, "raw_weather": None}

async def weather_error_node(state: AdvisorState) -> Dict[str, Any]:
    """Handles live weather API outage or communication failure without fabricating numbers."""
    loc_name = state.get("location") or "the requested location"
    return {
        "error": "weather_service_unavailable",
        "final_response": f"I couldn't retrieve live weather data for {loc_name} right now, so I can't provide a weather-based safety advisory.",
    }

async def match_sops_node(state: AdvisorState) -> Dict[str, Any]:
    """Evaluates deterministic SOP rules from config/sops.yaml against weather."""
    weather_dict = state.get("weather")
    intent_dict = state.get("intent") or {}
    activity = intent_dict.get("activity")
    target_groups = intent_dict.get("vulnerable_groups", [])

    if not weather_dict:
        return {"matched_sops": [], "sop_found": False}

    weather_obj = WeatherData(**weather_dict)
    matches = sop_engine.evaluate(
        weather=weather_obj,
        activity=activity,
        target_groups=target_groups,
    )

    if matches:
        matched_list = [
            {
                "id": m.sop.id,
                "name": m.sop.name,
                "category": m.sop.category,
                "severity": m.sop.severity,
                "priority": m.sop.priority,
                "advisory": m.sop.advisory,
                "action": m.sop.recommended_action,
                "matched_reasons": m.matched_conditions,
            }
            for m in matches
        ]
        return {"matched_sops": matched_list, "sop_found": True}

    return {"matched_sops": [], "sop_found": False}

async def no_sop_response_node(state: AdvisorState) -> Dict[str, Any]:
    """
    Handles cases where no SOP matches.

    If the user only asked for weather and no activity was identified,
    return the live weather information without inventing safety advice.

    If an activity was identified, explicitly report that no SOP applies.
    """

    intent = state.get("intent") or {}
    activity = intent.get("activity")

    location = state.get("location") or "the requested location"
    weather = state.get("weather") or {}

    temperature = weather.get("temperature")
    wind_speed = weather.get("wind_speed")
    weather_description = weather.get(
        "weather_description",
        "Unknown"
    )

    # Weather-only query
    if not activity:
        return {
            "error": None,
            "sop_found": False,
            "final_response": (
                f"Current weather in {location}: "
                f"Temperature: {temperature}°C, "
                f"Wind: {wind_speed} km/h, "
                f"Conditions: {weather_description}."
            ),
        }

    # Activity query with no matching SOP
    return {
        "error": None,
        "sop_found": False,
        "final_response": (
            f"No applicable SOP was found for {activity} "
            f"under the current weather conditions in {location} "
            f"(Temperature: {temperature}°C, "
            f"Wind: {wind_speed} km/h, "
            f"Weather: {weather_description}). "
            f"I therefore cannot provide a policy-backed "
            f"safety recommendation."
        ),
    }

async def resolve_conflicts_node(state: AdvisorState) -> Dict[str, Any]:
    """Deterministically sorts and selects the winning SOP based on priority, severity, and ID."""
    matched = state.get("matched_sops", [])
    if not matched:
        return {"selected_sop": None, "conflict_resolution": None}

    # Deterministic sort: Priority (descending) -> Severity Weight (descending) -> SOP ID (ascending)
    sorted_sops = sorted(
        matched,
        key=lambda s: (
            -int(s.get("priority", 0)),
            -SEVERITY_WEIGHTS.get(s.get("severity", ""), 0),
            str(s.get("id", ""))
        )
    )

    primary = sorted_sops[0]
    conflict_note = None
    if len(sorted_sops) > 1:
        conflict_note = (
            f"Multiple SOPs triggered ({', '.join([s['id'] for s in sorted_sops])}). "
            f"SOP '{primary['id']}' ({primary['name']}) takes precedence (Priority: {primary['priority']}, Severity: {primary['severity']})."
        )

    return {
        "matched_sops": sorted_sops,
        "selected_sop": primary,
        "conflict_resolution": conflict_note,
    }

async def generate_response_node(state: AdvisorState) -> Dict[str, Any]:
    """
    Generates a 100% SOP-grounded safety advisory citing exact SOP ID, name,
    actual observed weather metrics, conditions, and required actions.
    """
    selected = state.get("selected_sop")
    loc = state.get("location", "the requested location")
    w = state.get("weather", {})
    intent_dict = state.get("intent", {})
    activity = (intent_dict.get("activity") or "Outdoor Activity").title()
    conflict_note = state.get("conflict_resolution")
    matched_all = state.get("matched_sops", [])

    lines = []
    lines.append(f"## SOP Safety Advisory: **{activity}** in **{loc}**\n")

    # Actual weather observed
    lines.append(
        f"**Observed Weather Telemetry:** {w.get('weather_description')} | "
        f"Temperature: {w.get('temperature')}°C (Feels like {w.get('apparent_temperature')}°C) | "
        f"Wind: {w.get('wind_speed')} km/h (Gusts: {w.get('wind_gusts')} km/h) | "
        f"Humidity: {w.get('relative_humidity')}% | "
        f"UV Index: {w.get('uv_index')}\n"
    )

    # Primary Triggered SOP
    lines.append(f"### Primary Policy Applied: **[{selected['id']}] {selected['name']}**")
    lines.append(f"- **Severity Level:** `{selected['severity']}` (Priority: `{selected['priority']}`)")
    lines.append(f"- **Triggered Condition:** {'; '.join(selected['matched_reasons'])}")
    lines.append(f"- **Mandatory Directive:** {selected['advisory']}")
    lines.append(f"- **Required Action:** **{selected['action']}**\n")

    # If multiple SOPs matched
    if conflict_note:
        lines.append(f"### Conflict Resolution\n> {conflict_note}\n")
        if len(matched_all) > 1:
            lines.append("**Additional Triggered SOPs:**")
            for other in matched_all[1:]:
                lines.append(f"- `[{other['id']}] {other['name']}` ({other['severity']}): {other['action']}")
            lines.append("")

    final_text = "\n".join(lines)
    return {"final_response": final_text}

# ----------------- CONDITIONAL ROUTING -----------------

def route_after_understanding(state: AdvisorState) -> str:
    if state.get("adversarial_attempt"):
        return "adversarial_error"
    return "resolve_location"

def route_after_location(state: AdvisorState) -> str:
    if state.get("location_resolved"):
        return "fetch_weather"
    return "location_error"

def route_after_weather(state: AdvisorState) -> str:
    if state.get("weather_available"):
        return "match_sops"
    return "weather_error"

def route_after_sop_matching(state: AdvisorState) -> str:
    if state.get("sop_found"):
        return "resolve_conflicts"
    return "no_sop_response"

# ----------------- GRAPH COMPILATION -----------------

def build_advisor_graph():
    """Builds and compiles the real LangGraph StateGraph agent."""
    graph = StateGraph(AdvisorState)

    # Add Nodes
    graph.add_node("understand_question", understand_question_node)
    graph.add_node("adversarial_error", adversarial_error_node)
    graph.add_node("resolve_location", resolve_location_node)
    graph.add_node("location_error", location_error_node)
    graph.add_node("fetch_weather", fetch_weather_node)
    graph.add_node("weather_error", weather_error_node)
    graph.add_node("match_sops", match_sops_node)
    graph.add_node("no_sop_response", no_sop_response_node)
    graph.add_node("resolve_conflicts", resolve_conflicts_node)
    graph.add_node("generate_response", generate_response_node)

    # Add Edges & Conditional Branches
    graph.add_edge(START, "understand_question")

    graph.add_conditional_edges(
        "understand_question",
        route_after_understanding,
        {
            "adversarial_error": "adversarial_error",
            "resolve_location": "resolve_location",
        },
    )

    graph.add_edge("adversarial_error", END)

    graph.add_conditional_edges(
        "resolve_location",
        route_after_location,
        {
            "fetch_weather": "fetch_weather",
            "location_error": "location_error",
        },
    )

    graph.add_edge("location_error", END)

    graph.add_conditional_edges(
        "fetch_weather",
        route_after_weather,
        {
            "match_sops": "match_sops",
            "weather_error": "weather_error",
        },
    )

    graph.add_edge("weather_error", END)

    graph.add_conditional_edges(
        "match_sops",
        route_after_sop_matching,
        {
            "resolve_conflicts": "resolve_conflicts",
            "no_sop_response": "no_sop_response",
        },
    )

    graph.add_edge("no_sop_response", END)
    graph.add_edge("resolve_conflicts", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()

advisor_graph = build_advisor_graph()
