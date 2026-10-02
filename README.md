# 🌤️ AeroSOP | AI Weather Advisory & Safety Intelligence Hub

An advanced, AI-powered outdoor safety and weather advisory application combining real-time meteorological telemetry from Open-Meteo with a **deterministic Standard Operating Procedure (SOP) safety compliance engine**.

---

## 🌟 Key Features

1. **⚡ Deterministic SOP Safety Rule Engine**:
   - Evaluates complex weather rules configured in `config/sops.yaml`.
   - Supports `all_of`, `any_of`, temperature extremes, wind gusts, wind chill, precipitation rates, visibility, UV index, marine wave height, and thunderstorm detection.
   - Deterministic prioritization and severity weighting (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `ADVISORY`).
   - Immutable safety directives that prevent AI hallucinations or policy overrides.

2. **🧠 Conversational AI Advisor & Copilot**:
   - Natural language intent extraction for outdoor activities (cycling, running, hiking, open water swimming, drone flight, sports, walking).
   - Vulnerable demographic detection (children, elderly, pregnancy, respiratory/asthma).
   - Dynamic safety score rating (0–100) with visual radial gauge.
   - Contextual gear and preparedness checklist.
   - Text-to-speech audio synthesis and browser voice input dictation.
   - Adversarial prompt injection defense to guard against jailbreaks and safety bypass attempts.

3. **🔬 Interactive SOP Sandbox & Weather Lab**:
   - Real-time environmental parameter sliders (Temperature, Wind Speed, Gusts, Rain, UV Index, Visibility, Lightning Risk).
   - Instant visual rule firing and condition match breakdown.
   - One-click presets: *Severe Storm*, *Extreme Heat*, *Gale Wind*, *Sub-Zero Freeze*, and *Clear*.

4. **🗺️ SOP Rules Matrix Explorer**:
   - Full visual inspection of all active SOP definitions, target activities, condition thresholds, and mandatory directives.

---

## 🛠️ Architecture & Tech Stack

- **Backend**: FastAPI, Pydantic v2, PyYAML, HTTPX, Uvicorn.
- **Meteorology**: Open-Meteo Geocoding & Forecast APIs (with offline simulation fallback).
- **Frontend**: Glassmorphic UI with CSS3 custom properties, Google Fonts (*Outfit* & *Inter*), Font Awesome, Web Speech API.

---

## 🚀 Quick Start

### 1. Run the Server
```bash
python run.py
```
Or with Uvicorn:
```bash
uvicorn backend.main:app --reload --port 8000
```

### 2. Open in Browser
Visit: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### 3. Run Automated Tests
```bash
python -m pytest tests/
```

---

## 📡 API Endpoints

- `GET /api/health` - Server health status and loaded SOP count.
- `GET /api/sops` - List of all standard operating procedures.
- `POST /api/weather/lookup` - Real-time weather and forecast for any city.
- `POST /api/advisor/chat` - Natural language query advisory evaluation.
- `POST /api/sop/simulate` - Live parameter simulation for arbitrary environmental conditions.
- `GET /api/activities` - Recognized activities and demographic categories.
