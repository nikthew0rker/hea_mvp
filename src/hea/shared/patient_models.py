from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PatientSymptomIntake(BaseModel):
    summary: str | None = None
    symptoms: list[str] = []
    suspected_topics: list[str] = []
    duration: str | None = None
    severity: Literal["unknown", "mild", "moderate", "severe"] = "unknown"
    free_text: str | None = None


class PatientIntentDecision(BaseModel):
    next_action: Literal[
        "RESET_AND_GREET",
        "RESET_TO_FREE",
        "SHOW_CAPABILITIES",
        "RED_FLAG_GUIDANCE",
        "SEARCH",
        "SELECT_CANDIDATE",
        "RESTATE_CONSENT",
        "DECLINE",
        "START_ASSESSMENT",
        "PAUSE",
        "RESUME",
        "CANCEL",
        "SHOW_PAUSED",
        "SHOW_CURRENT_RESULT",
        "SHOW_CURRENT_REPORT",
        "EXPLAIN_CURRENT_RESULT",
        "SHOW_LAST_RESULT",
        "SHOW_LAST_REPORT",
        "EXPLAIN_LAST_RESULT",
        "SHOW_POST_OPTIONS",
        "RUN_RUNTIME_SUBGRAPH",
    ] = "SEARCH"
    confidence: float = 0.5
    rationale: str | None = None
    red_flag_level: Literal["none", "urgent", "emergency"] = "none"
    clarification_question: str | None = None
    selected_candidate_index: int | None = None
    symptom_summary: str | None = None
