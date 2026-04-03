from __future__ import annotations

from typing import Any, TypedDict


class PatientState(TypedDict, total=False):
    conversation_id: str
    language: str
    user_message: str

    mode: str
    selected_graph_id: str | None
    discovered_graphs: list[str]
    consent_status: str | None

    assessment_state: dict[str, Any] | None
    selected_graph: dict[str, Any] | None
    last_result: dict[str, Any] | None

    assistant_reply: str
    next_action: str
    candidates: list[dict[str, Any]]
    analyst_decision: dict[str, Any] | None
    red_flag_status: str | None
    symptom_summary: str | None
    last_search_query: str | None
    symptom_intake: dict[str, Any] | None
