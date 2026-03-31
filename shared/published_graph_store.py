from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.graph_registry import upsert_graph_in_registry
from shared.json_store import JSONStore


DATA_DIR = Path("data")

ACTIVE_GRAPH_STORE = JSONStore(
    DATA_DIR / "active_graph.json",
    default={
        "graph_id": None,
        "status": None,
        "is_active": False,
        "published_at": None,
        "metadata": {},
        "graph": None,
    },
)


def _ensure_data_dir() -> None:
    """
    Ensure that the local data directory and backing JSON files exist.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_GRAPH_STORE.ensure_exists()


def publish_graph(graph_id: str, graph_payload: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Publish a graph by writing it into local shared storage and registry.

    Behavior:
    - active_graph.json keeps the most recently published graph
    - graph_registry.json accumulates all published graphs as a searchable library
    """
    _ensure_data_dir()

    record = {
        "graph_id": graph_id,
        "status": "published",
        "is_active": True,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
        "graph": graph_payload,
    }

    ACTIVE_GRAPH_STORE.save(record)
    registry_entry = upsert_graph_in_registry(graph_id, graph_payload, metadata or {})

    return {
        "graph_id": graph_id,
        "active_graph_file": str(ACTIVE_GRAPH_STORE.path),
        "registry_entry": registry_entry,
    }


def load_active_graph_record() -> dict[str, Any] | None:
    """
    Load the currently active graph record.
    """
    _ensure_data_dir()
    payload = ACTIVE_GRAPH_STORE.load()
    return payload if isinstance(payload, dict) else None


def load_active_graph() -> dict[str, Any] | None:
    """
    Load only the active graph payload.
    """
    record = load_active_graph_record()
    if not record:
        return None
    graph = record.get("graph")
    return graph if isinstance(graph, dict) else None


def get_active_graph_id() -> str | None:
    """
    Return the current active graph id, if any.
    """
    record = load_active_graph_record()
    if not record:
        return None
    graph_id = record.get("graph_id")
    return graph_id if isinstance(graph_id, str) else None
