from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hea.shared.db import dumps, get_conn, init_db, loads


def load_patient_session(conversation_id: str) -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT state_json FROM patient_sessions WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return loads(row["state_json"], {}) if row else {}


def save_patient_session(conversation_id: str, state: dict[str, Any]) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO patient_sessions (conversation_id, state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            ''',
            (conversation_id, dumps(state), datetime.now(timezone.utc).isoformat()),
        )


def load_specialist_session(conversation_id: str) -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT state_json FROM specialist_sessions WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return loads(row["state_json"], {}) if row else {}


def save_specialist_session(conversation_id: str, state: dict[str, Any]) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO specialist_sessions (conversation_id, state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            ''',
            (conversation_id, dumps(state), datetime.now(timezone.utc).isoformat()),
        )
