import secrets
from typing import Dict, Optional

SESSION_STORE: Dict[str, str] = {}

def generate_session_id() -> str:
    """Generate a unique session ID."""
    return secrets.token_urlsafe(32)

def store_uuid(session_id: str, uuid: str) -> None:
    """Store UUID in the session store."""
    SESSION_STORE[session_id] = uuid

def get_uuid(session_id: str) -> Optional[str]:
    """Retrieve UUID from the session store."""
    return SESSION_STORE.get(session_id)

def clear_session(session_id: str) -> None:
    """Remove session ID from the store."""
    SESSION_STORE.pop(session_id, None)