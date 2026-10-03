import re
from typing import List, Optional
from backend.sop.models import IntentExtraction

ACTIVITY_KEYWORDS = {
    "cycling": [
        "cycling", "biking", "bike", "bicycle", "cycle", "ride a bike", "ride my bike",
        "bicycled", "take my bike out", "take my bicycle out", "bike ride", "biking outside",
        "go cycling", "cycling trip", "ride outside", "pedaling", "e-bike", "scooter", "e-scooter"
    ],
    "running": [
        "running", "jogging", "jog", "run", "marathon", "sprint", "trail run",
        "jog outside", "go for a jog", "go for a run", "morning run", "evening run",
        "run outside", "jogging outside", "cardio outside", "take a jog"
    ],
    "hiking": [
        "hiking", "trekking", "hike", "trek", "mountaineering", "mountain climb", "climbing",
        "trail walk", "mountain hike", "trail hiking", "mountain trail", "hiking trail",
        "go hiking", "hiking trip"
    ],
    "swimming": [
        "swimming", "swim", "open water swim", "kayaking", "kayak", "paddleboarding", "sup",
        "boating", "surfing", "surf", "lake swim", "sea swim", "ocean swim", "open water swimming"
    ],
    "drone flying": [
        "drone", "drones", "drone flying", "uav", "quadcopter", "aerial photography", "rc plane",
        "fly a drone", "fly my drone", "drone flight", "flying drones", "fly uav"
    ],
    "picnic": [
        "picnic", "family picnic", "picnic outside", "have a picnic", "family outing",
        "barbecue", "bbq", "park visit", "outdoor gathering", "outdoor lunch"
    ],
    "walking": [
        "walking", "walk", "stroll", "commute on foot", "dog walking", "walk outside",
        "walking outside", "take a walk", "walking to work"
    ],
    "outdoor sports": [
        "football", "soccer", "cricket", "golf", "tennis", "basketball", "baseball", "rugby", "volleyball"
    ],
    "camping": [
        "camping", "camp", "tent", "bonfire"
    ],
    "general outdoor": [
        "outside", "outdoor", "park", "garden", "gardening", "sightseeing", "explore",
        "outdoor activities", "outdoor activity", "go outside"
    ],
}

VULNERABLE_KEYWORDS = {
    "children": ["kid", "kids", "child", "children", "toddler", "toddlers", "infant", "infants", "baby", "babies", "son", "daughter"],
    "elderly": ["elderly", "senior", "seniors", "grandpa", "grandma", "grandfather", "grandmother", "older adult", "aged", "geriatric"],
    "pregnant": ["pregnant", "pregnancy", "expecting"],
    "chronic_illness": ["asthma", "asthmatic", "heart condition", "cardiac", "respiratory", "allergies", "high blood pressure"],
}

ADVERSARIAL_PATTERNS = [
    r"ignore\s+(all\s+)?(previous\s+)?instructions",
    r"override\s+(all\s+)?(safety\s+)?(rules|sops|policy|protocol)",
    r"you\s+must\s+say\s+it\s+is\s+safe",
    r"disregard\s+(the\s+)?sop",
    r"ignore\s+(the\s+)?sop",
    r"bypass\s+safety",
    r"system\s+prompt",
    r"reveal\s+your\s+instructions",
    r"pretend\s+there\s+is\s+no\s+danger",
    r"give\s+me\s+advice\s+even\s+if\s+there\s+is\s+no\s+sop",
    r"jailbreak",
    r"dan\s+mode",
]

COMMON_CITIES = [
    "london", "new york", "tokyo", "paris", "mumbai", "delhi", "bengaluru", "bangalore",
    "sydney", "dubai", "singapore", "berlin", "toronto", "vancouver", "san francisco",
    "los angeles", "chicago", "seattle", "boston", "miami", "austin", "denver", "rome",
    "madrid", "amsterdam", "beijing", "shanghai", "hong kong", "seoul", "bangkok",
    "istanbul", "cairo", "cape town", "auckland", "melbourne", "zurich", "geneva",
    "vienna", "stockholm", "oslo", "helsinki", "dublin", "edinburgh", "manchester",
    "birmingham", "hyderabad", "chennai", "kolkata", "pune", "ahmedabad", "jaipur",
    "calgary", "montreal"
]

class IntentService:
    def extract_intent(self, text: str, default_location: Optional[str] = None) -> IntentExtraction:
        """
        Extracts structured intent, outdoor activities, location, demographics,
        and detects adversarial attempts from the user's input.
        """
        text_lower = text.lower().strip()

        # 1. Adversarial Detection
        adversarial = False
        for pat in ADVERSARIAL_PATTERNS:
            if re.search(pat, text_lower):
                adversarial = True
                break

        # 2. Activity Extraction
        matched_activity = None
        for canonical, variants in ACTIVITY_KEYWORDS.items():
            for v in variants:
                if re.search(rf"\b{re.escape(v)}\b", text_lower):
                    matched_activity = canonical
                    break
            if matched_activity:
                break

        if not matched_activity:
            try:
                from backend.graph.agent import sop_engine
                for sop in sop_engine.get_all_sops():
                    for act in sop.activities:
                        if re.search(rf"\b{re.escape(act.lower())}\b", text_lower):
                            matched_activity = act.lower()
                            break
                    if matched_activity:
                        break
            except Exception:
                pass

        # 3. Vulnerable Demographic Groups
        matched_groups: List[str] = []
        for group, keywords in VULNERABLE_KEYWORDS.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                    if group not in matched_groups:
                        matched_groups.append(group)
                    break

        # 4. Time Reference Extraction
        time_ref = None
        time_patterns = [
            (r"\b(right now|currently|current|at the moment)\b", "now"),
            (r"\b(this morning|morning)\b", "this morning"),
            (r"\b(this afternoon|afternoon)\b", "this afternoon"),
            (r"\b(this evening|tonight|evening)\b", "this evening"),
            (r"\b(tomorrow morning)\b", "tomorrow morning"),
            (r"\b(tomorrow afternoon)\b", "tomorrow afternoon"),
            (r"\b(tomorrow evening|tomorrow night)\b", "tomorrow evening"),
            (r"\b(tomorrow)\b", "tomorrow"),
            (r"\b(this weekend|saturday|sunday)\b", "this weekend"),
            (r"\b(today)\b", "today"),
        ]
        for pat, t_label in time_patterns:
            if re.search(pat, text_lower):
                time_ref = t_label
                break

        # 5. Location Extraction
        extracted_location = None

        loc_patterns = [
            r"\b(?:weather in|weather for)\s+([A-Za-z\s]+?)(?:\s+(?:today|tomorrow|now|this)|\s*[,.?!]|\s*$)",
            r"\b(?:visiting|heading to|traveling to|going to)\s+([A-Za-z\s]+?)(?:\s+(?:today|tomorrow|now|this|with|for|at|is|can|should)|\s*[,.?!]|\s*$)",
            r"\b(?:in|at|near|around)\s+([A-Za-z\s]+?)(?:\s+(?:today|tomorrow|now|this|with|for|at|is|can|should)|\s*[,.?!]|\s*$)",
            r"\bfor\s+([A-Za-z\s]+?)(?:\s+(?:today|tomorrow|now|this|with|for|at|is|can|should)|\s*[,.?!]|\s*$)",
        ]

        invalid_locs = {
            "the", "a", "an", "my", "our", "outdoor", "park", "morning",
            "afternoon", "evening", "tomorrow", "today", "now", "safe",
            "general", "very", "extreme", "strong", "severe"
        }

        for pat in loc_patterns:
            for match in re.finditer(pat, text, re.IGNORECASE):
                candidate = match.group(1).strip()
                words = candidate.lower().split()
                if candidate.lower() not in invalid_locs and len(candidate) > 2:
                    if words and words[0] in {"a", "an", "the", "my", "our"}:
                        continue
                    extracted_location = candidate
                    break
            if extracted_location:
                break

        if not extracted_location:
            for city in COMMON_CITIES:
                if re.search(rf"\b{re.escape(city)}\b", text_lower):
                    extracted_location = city.title()
                    break

        final_location = extracted_location or default_location

        return IntentExtraction(
            activity=matched_activity,
            location=final_location,
            time_reference=time_ref or "current",
            vulnerable_groups=matched_groups,
            travel_context=None,
            adversarial_attempt=adversarial,
            clarification_needed=bool(not final_location),
        )

intent_service = IntentService()
