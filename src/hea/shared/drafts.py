from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hea.shared.db import dumps, get_conn, init_db, loads
from hea.shared.models import default_draft


def load_specialist_draft(conversation_id: str) -> dict[str, Any]:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT draft_json FROM specialist_drafts WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return loads(row["draft_json"], default_draft()) if row else default_draft()


def save_specialist_draft(conversation_id: str, draft: dict[str, Any]) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO specialist_drafts (conversation_id, draft_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                draft_json = excluded.draft_json,
                updated_at = excluded.updated_at
            ''',
            (conversation_id, dumps(draft), datetime.now(timezone.utc).isoformat()),
        )


def save_specialist_draft_version(
    conversation_id: str,
    draft: dict[str, Any],
    operation: dict[str, Any] | None = None,
    note: str | None = None,
) -> int:
    init_db()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            '''
            INSERT INTO specialist_draft_versions (conversation_id, draft_json, operation_json, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                conversation_id,
                dumps(draft),
                dumps(operation) if operation else None,
                note,
                created_at,
            ),
        )
        return int(cursor.lastrowid)


def list_specialist_draft_versions(conversation_id: str, limit: int = 10) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            '''
            SELECT version_id, draft_json, operation_json, note, created_at
            FROM specialist_draft_versions
            WHERE conversation_id = ?
            ORDER BY version_id DESC
            LIMIT ?
            ''',
            (conversation_id, limit),
        ).fetchall()
        return [
            {
                "version_id": row["version_id"],
                "draft": loads(row["draft_json"], default_draft()),
                "operation": loads(row["operation_json"], None),
                "note": row["note"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def load_specialist_draft_version(conversation_id: str, version_id: int) -> dict[str, Any] | None:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            '''
            SELECT draft_json FROM specialist_draft_versions
            WHERE conversation_id = ? AND version_id = ?
            ''',
            (conversation_id, version_id),
        ).fetchone()
        return loads(row["draft_json"], default_draft()) if row else None


def log_specialist_audit_event(conversation_id: str, event_type: str, payload: dict[str, Any]) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO specialist_audit_events (conversation_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            ''',
            (conversation_id, event_type, dumps(payload), datetime.now(timezone.utc).isoformat()),
        )
