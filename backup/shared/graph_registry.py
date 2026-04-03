from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.json_store import JSONStore


DATA_DIR = Path("data")
GRAPH_REGISTRY_STORE = JSONStore(DATA_DIR / "graph_registry.json", default=[])


def _ensure_store() -> None:
    """
    Ensure the graph registry store exists.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_REGISTRY_STORE.ensure_exists()


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_]+", text.lower())
        if len(token) >= 3
    }


def _collect_question_texts(graph_payload: dict[str, Any]) -> list[str]:
    texts: list[str] = []

    questions = graph_payload.get("questions")
    if isinstance(questions, list):
        for q in questions:
            if isinstance(q, dict):
                text = q.get("text")
                if isinstance(text, str):
                    texts.append(text)

    source_draft = graph_payload.get("source_draft", {})
    if isinstance(source_draft, dict):
        draft_questions = source_draft.get("candidate_questions")
        if isinstance(draft_questions, list):
            for q in draft_questions:
                if isinstance(q, dict):
                    text = q.get("text")
                    if isinstance(text, str):
                        texts.append(text)

    return texts


def derive_graph_metadata(graph_id: str, graph_payload: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Derive searchable metadata for a graph.

    This keeps the registry graph-agnostic while still giving the patient
    orchestrator enough information to search the graph library.
    """
    metadata = metadata or {}

    title = (
        graph_payload.get("title")
        or graph_payload.get("topic")
        or (graph_payload.get("source_draft", {}) or {}).get("understood", {}).get("topic")
        or graph_id
    )

    topic = (
        graph_payload.get("topic")
        or (graph_payload.get("source_draft", {}) or {}).get("understood", {}).get("topic")
        or title
    )

    questions = graph_payload.get("questions")
    if isinstance(questions, list):
        questions_count = len(questions)
    else:
        source_draft = graph_payload.get("source_draft", {})
        if isinstance(source_draft, dict) and isinstance(source_draft.get("candidate_questions"), list):
            questions_count = len(source_draft.get("candidate_questions"))
        else:
            questions_count = 0

    estimated_time_minutes = max(1, (questions_count + 2) // 3) if questions_count else 2

    question_texts = _collect_question_texts(graph_payload)
    seed_text = " ".join([str(title), str(topic)] + question_texts[:8])

    tags = set()
    tags.update(_tokenize(str(topic)))
    tags.update(_tokenize(str(title)))

    provided_tags = metadata.get("tags")
    if isinstance(provided_tags, list):
        for tag in provided_tags:
            if isinstance(tag, str):
                tags.add(tag.lower())

    entry_signals = metadata.get("entry_signals")
    if not isinstance(entry_signals, list):
        entry_signals = sorted(list(tags))[:8]

    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        description = f"Assessment related to {topic}"

    return {
        "title": title,
        "topic": topic,
        "description": description,
        "tags": sorted(list(tags)),
        "entry_signals": entry_signals,
        "questions_count": questions_count,
        "estimated_time_minutes": estimated_time_minutes,
        "search_text": seed_text,
    }


def upsert_graph_in_registry(graph_id: str, graph_payload: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Insert or update a graph entry in the library registry.
    """
    _ensure_store()
    payload = GRAPH_REGISTRY_STORE.load()
    if not isinstance(payload, list):
        payload = []

    derived_metadata = derive_graph_metadata(graph_id, graph_payload, metadata)

    entry = {
        "graph_id": graph_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "published": True,
        "metadata": derived_metadata,
        "graph": graph_payload,
    }

    replaced = False
    for idx, item in enumerate(payload):
        if isinstance(item, dict) and item.get("graph_id") == graph_id:
            payload[idx] = entry
            replaced = True
            break

    if not replaced:
        payload.append(entry)

    GRAPH_REGISTRY_STORE.save(payload)
    return entry


def load_graph_library() -> list[dict[str, Any]]:
    """
    Load all graph entries from registry.
    """
    _ensure_store()
    payload = GRAPH_REGISTRY_STORE.load()
    return payload if isinstance(payload, list) else []


def get_graph_record(graph_id: str) -> dict[str, Any] | None:
    """
    Return one graph registry entry by id.
    """
    for item in load_graph_library():
        if isinstance(item, dict) and item.get("graph_id") == graph_id:
            return item
    return None


def search_graphs(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Search graph library using simple heuristic scoring.

    This intentionally stays graph-agnostic and does not assume a specific domain.
    """
    query_tokens = _tokenize(query)
    query_lower = query.lower()

    results: list[dict[str, Any]] = []
    for item in load_graph_library():
        if not isinstance(item, dict):
            continue

        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            continue

        title = str(metadata.get("title", ""))
        description = str(metadata.get("description", ""))
        topic = str(metadata.get("topic", ""))
        tags = metadata.get("tags", [])
        entry_signals = metadata.get("entry_signals", [])
        search_text = str(metadata.get("search_text", ""))

        score = 0.0
        reasons: list[str] = []

        meta_text = " ".join(
            [title, description, topic, search_text]
            + [str(t) for t in tags if isinstance(t, str)]
            + [str(s) for s in entry_signals if isinstance(s, str)]
        )
        meta_tokens = _tokenize(meta_text)

        overlap = query_tokens & meta_tokens
        if overlap:
            score += float(len(overlap)) * 2.0
            reasons.append(f"token overlap: {', '.join(sorted(list(overlap))[:4])}")

        for signal in entry_signals:
            if isinstance(signal, str) and signal.lower() in query_lower:
                score += 4.0
                reasons.append(f"matched signal: {signal}")

        for tag in tags:
            if isinstance(tag, str) and tag.lower() in query_lower:
                score += 3.0
                reasons.append(f"matched tag: {tag}")

        if title and title.lower() in query_lower:
            score += 4.0
            reasons.append("matched title")

        if topic and topic.lower() in query_lower:
            score += 3.0
            reasons.append("matched topic")

        if score > 0:
            results.append(
                {
                    "graph_id": item.get("graph_id"),
                    "score": score,
                    "reason": "; ".join(reasons[:3]),
                    "metadata": metadata,
                    "graph": item.get("graph"),
                }
            )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def list_graph_summaries(limit: int = 10) -> list[dict[str, Any]]:
    """
    Return lightweight graph summaries for capabilities listing.
    """
    summaries: list[dict[str, Any]] = []
    for item in load_graph_library()[:limit]:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        summaries.append(
            {
                "graph_id": item.get("graph_id"),
                "title": metadata.get("title") or item.get("graph_id"),
                "description": metadata.get("description"),
                "questions_count": metadata.get("questions_count"),
                "estimated_time_minutes": metadata.get("estimated_time_minutes"),
                "tags": metadata.get("tags", []),
            }
        )
    return summaries
