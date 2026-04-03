from __future__ import annotations

from typing import Any, TypedDict


class SpecialistState(TypedDict, total=False):
    conversation_id: str
    language: str
    user_message: str

    draft: dict[str, Any]
    pending_proposal: dict[str, Any] | None
    analyst_decision: dict[str, Any] | None
    edit_operation: dict[str, Any] | None
    critic_review: dict[str, Any] | None
    compile_result: dict[str, Any] | None
    publish_result: dict[str, Any] | None

    assistant_reply: str
    next_action: str
