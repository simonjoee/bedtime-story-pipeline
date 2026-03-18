import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "default-secret-change-me")
REQUIRE_LOGIN = os.getenv("REQUIRE_LOGIN", "true").lower() == "true"

sessions: dict = {}

COOKIE_NAME = "session_id"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60


def verify_password(password: str) -> bool:
    if not ADMIN_PASSWORD:
        return False
    return secrets.compare_digest(password, ADMIN_PASSWORD)


def create_session() -> str:
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(seconds=COOKIE_MAX_AGE)
    }
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    if not session_id or session_id not in sessions:
        return None
    
    session = sessions[session_id]
    if datetime.now() > session["expires_at"]:
        del sessions[session_id]
        return None
    
    return session


def delete_session(session_id: str) -> None:
    if session_id in sessions:
        del sessions[session_id]


def cleanup_expired_sessions() -> None:
    now = datetime.now()
    expired = [sid for sid, s in sessions.items() if now > s["expires_at"]]
    for sid in expired:
        del sessions[sid]
