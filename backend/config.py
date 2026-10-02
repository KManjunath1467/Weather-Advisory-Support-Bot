import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseModel):
    app_name: str = "Weather-Advisory Support Bot"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # LLM Settings
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm_temperature: float = 0.0
    
    # SOP File Path
    sop_file_path: Path = BASE_DIR / "config" / "sops.yaml"
    
    # Weather API Settings
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    geocoding_base_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    weather_request_timeout: float = 10.0
    
    # Default fallback location if user mentions activity without location and no session context
    default_location: str | None = None

settings = Settings()
