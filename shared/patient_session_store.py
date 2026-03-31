from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.json_store import JSONStore


DATA_DIR = Path("data")
SESSION_STORE = JSONStore(DATA_DIR / "patient_sessions.json", default={})


def _ensure_store() -> None:
    """
    Ensure the patient session store exists.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_STORE.ensure_exists()


def load_session(conversation_id: str) -> dict[str, Any] | None:
    """
    Load one patient session by conversation id.
    """
    _ensure_store()
    payload = SESSION_STORE.load()
    if not isinstance(payload, dict):
        return None
    session = payload.get(conversation_id)
    return session if isinstance(session, dict) else None


def save_session(conversation_id: str, session: dict[str, Any]) -> dict[str, Any]:
    """
    Save one patient session by conversation id.
    """
    _ensure_store()
    payload = SESSION_STORE.load()
    if not isinstance(payload, dict):
        payload = {}
    payload[conversation_id] = session
    SESSION_STORE.save(payload)
    return session


def delete_session(conversation_id: str) -> None:
    """
    Delete one patient session.
    """
    _ensure_store()
    payload = SESSION_STORE.load()
    if not isinstance(payload, dict):
        payload = {}
    payload.pop(conversation_id, None)
    SESSION_STORE.save(payload)
