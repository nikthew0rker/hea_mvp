from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hea.shared.db import dumps, get_conn, init_db, loads


def upsert_graph(graph: dict[str, Any]) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            '''
            INSERT INTO graphs (graph_id, title, topic, description, tags_json, entry_signals_json, graph_json, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(graph_id) DO UPDATE SET
                title = excluded.title,
                topic = excluded.topic,
                description = excluded.description,
                tags_json = excluded.tags_json,
                entry_signals_json = excluded.entry_signals_json,
                graph_json = excluded.graph_json,
                published_at = excluded.published_at
            ''',
            (
                graph["graph_id"],
                graph["title"],
                graph["topic"],
                graph.get("description", ""),
                dumps(graph.get("tags", [])),
                dumps(graph.get("entry_signals", [])),
                dumps(graph),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_graph(graph_id: str) -> dict[str, Any] | None:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT graph_json FROM graphs WHERE graph_id = ?", (graph_id,)).fetchone()
        return loads(row["graph_json"], None) if row else None


def list_graphs() -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT graph_json FROM graphs ORDER BY published_at DESC").fetchall()
        return [loads(row["graph_json"], {}) for row in rows]
