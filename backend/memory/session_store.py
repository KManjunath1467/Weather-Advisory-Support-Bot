from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class SessionData(BaseModel):
    session_id: str
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    activity: Optional[str] = None
    vulnerable_groups: List[str] = Field(default_factory=list)
    history: List[Dict[str, str]] = Field(default_factory=list)

class SessionStore:
    """
    In-memory session manager maintaining conversation context across turns.
    Enables multi-turn references (e.g. Turn 1: 'Weather in Bengaluru', Turn 2: 'Can I go cycling?').
    """

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}

    def get_or_create(self, session_id: str) -> SessionData:
        if not session_id:
            session_id = "default-session"
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionData(session_id=session_id)
        return self._sessions[session_id]

    def update(self, session_id: str, **kwargs) -> SessionData:
        session = self.get_or_create(session_id)
        for key, val in kwargs.items():
            if hasattr(session, key) and val is not None:
                setattr(session, key, val)
        return session

    def add_history(self, session_id: str, role: str, content: str) -> None:
        session = self.get_or_create(session_id)
        session.history.append({"role": role, "content": content})

    def clear(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]

session_store = SessionStore()
