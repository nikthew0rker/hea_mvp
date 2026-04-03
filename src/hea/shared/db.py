from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from hea.shared.config import get_settings


def _resolved_db_path() -> Path:
    settings = get_settings()
    path = settings.db_path
    if path.exists() and path.is_dir():
        raise RuntimeError(f"Database path points to a directory, not a file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    path = _resolved_db_path()
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(max_retries: int = 8, retry_delay: float = 0.35) -> None:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with get_conn() as conn:
                conn.executescript(
                    '''
                    CREATE TABLE IF NOT EXISTS graphs (
                        graph_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        description TEXT NOT NULL,
                        tags_json TEXT NOT NULL,
                        entry_signals_json TEXT NOT NULL,
                        graph_json TEXT NOT NULL,
                        published_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS specialist_drafts (
                        conversation_id TEXT PRIMARY KEY,
                        draft_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS specialist_draft_versions (
                        version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id TEXT NOT NULL,
                        draft_json TEXT NOT NULL,
                        operation_json TEXT,
                        note TEXT,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS specialist_audit_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS specialist_sessions (
                        conversation_id TEXT PRIMARY KEY,
                        state_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS patient_sessions (
                        conversation_id TEXT PRIMARY KEY,
                        state_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    '''
                )
            return
        except sqlite3.OperationalError as exc:
            last_error = exc
            message = str(exc).lower()
            # transient startup race / Docker Desktop mount weirdness
            if "disk i/o error" in message or "database is locked" in message or "readonly" in message:
                time.sleep(retry_delay * attempt)
                continue
            raise

    raise RuntimeError(f"Failed to initialize SQLite database after {max_retries} attempts: {last_error}") from last_error


def dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default
