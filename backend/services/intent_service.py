import re
from typing import List, Optional
from backend.sop.models import IntentExtraction

# Known activities mapped to canonical categories
ACTIVITY_KEYWORDS = {
    "cycling": ["cycling", "biking", "bike", "bicycle", "cycle", "ride a bike", "bicycled"],
    "running": ["running", "jogging", "jog", "run", "marathon", "sprint", "trail run"],
    "hiking": ["hiking", "trekking", "hike", "trek", "mountaineering", "mountain climb", "climbing"],
    "swimming": ["swimming", "swim", "open water swim", "kayaking", "kayak", "paddleboarding", "sup", "boating", "surfing", "surf"],
    "drone flying": ["drone", "drones", "drone flying", "uav", "quadcopter", "aerial photography", "rc plane"],
    "walking": ["walking", "walk", "stroll", "commute on foot", "dog walking"],
    "outdoor sports": ["football", "soccer", "cricket", "golf", "tennis", "basketball", "baseball", "rugby", "volleyball"],
    "camping": ["camping", "camp", "tent", "bonfire"],
    "general outdoor": ["outside", "outdoor", "picnic", "park", "garden", "gardening", "sightseeing", "explore"],
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
    r"disregard\s+sop",
    r"bypass\s+safety",
    r"system\s+prompt",
    r"reveal\s+your\s+instructions",
    r"pretend\s+there\s+is\s+no\s+danger",
    r"jailbreak",
    r"dan\s+mode",
]

COMMON_CITIES = [
    "london", "new york", "tokyo", "paris", "mumbai", "delhi", "bangalore", "sydney", "dubai", "singapore",
    "berlin", "toronto", "vancouver", "san francisco", "los angeles", "chicago", "seattle", "boston",
    "miami", "austin", "denver", "rome", "madrid", "amsterdam", "beijing", "shanghai", "hong kong",
    "seoul", "bangkok", "istanbul", "cairo", "cape town", "auckland", "melbourne", "zurich", "geneva",
    "vienna", "stockholm", "oslo", "helsinki", "dublin", "edinburgh", "manchester", "birmingham",
    "hyderabad", "chennai", "kolkata", "pune", "ahmedabad", "jaipur", "calgary", "montreal"
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

        # 3. Vulnerable / Target Demographic Groups
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

        # Check for explicit "in <City>", "at <City>", "for <City>", "near <City>", "around <City>"
        loc_patterns = [
            r"\b(?:in|at|near|around|for)\s+([A-Za-z\s]+?)(?:\s+(?:today|tomorrow|now|this|with|for|at|is|can|should|,|\.|\?|$))",
            r"\b(?:visiting|heading to|traveling to|going to)\s+([A-Za-z\s]+?)(?:\s+(?:today|tomorrow|now|this|with|for|at|is|can|should|,|\.|\?|$))",
        ]

        for pat in loc_patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # Exclude common stop words or activity words mistaken as location
                invalid_locs = {"the", "a", "an", "my", "our", "outdoor", "park", "morning", "afternoon", "evening", "tomorrow", "today", "now"}
                if candidate.lower() not in invalid_locs and len(candidate) > 2:
                    extracted_location = candidate
                    break

        # If not found via regex preposition, check known cities list
        if not extracted_location:
            for city in COMMON_CITIES:
                if re.search(rf"\b{re.escape(city)}\b", text_lower):
                    extracted_location = city.title()
                    break

        # Fallback to default if provided
        final_location = extracted_location or default_location

        # Clarification check
        clarification = False
        if not final_location:
            clarification = True

        return IntentExtraction(
            activity=matched_activity or "general outdoor",
            location=final_location,
            time_reference=time_ref or "current",
            vulnerable_groups=matched_groups,
            travel_context=None,
            adversarial_attempt=adversarial,
            clarification_needed=clarification,
        )

intent_service = IntentService()
