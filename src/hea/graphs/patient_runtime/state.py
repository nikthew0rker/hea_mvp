from __future__ import annotations

from typing import Any, TypedDict


class PatientRuntimeState(TypedDict, total=False):
    graph: dict[str, Any]
    assessment_state: dict[str, Any]
    user_message: str
    assistant_reply: str
    next_action: str
