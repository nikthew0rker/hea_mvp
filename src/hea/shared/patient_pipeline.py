from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from hea.shared.model_router import controller_client
from hea.shared.patient_models import PatientIntentDecision, PatientSymptomIntake
from hea.shared.runtime import detect_language, infer_turn_language


RED_FLAG_PATTERNS = {
    "emergency": [
        r"боль в груди",
        r"не могу дышать",
        r"потер[яи] сознания",
        r"suicid",
        r"chest pain",
        r"shortness of breath",
        r"passed out",
    ],
    "urgent": [
        r"кровотеч",
        r"кровь идет",
        r"идет кровь",
        r"высокая температура",
        r"сильная боль",
        r"bleeding",
        r"high fever",
        r"severe pain",
    ],
}


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


CONCEPT_SYNONYMS = {
    "diabetes": [
        "diabetes",
        "diabet",
        "diabetic",
        "glucose",
        "blood glucose",
        "blood sugar",
        "sugar",
        "glycemia",
        "hyperglycemia",
        "diabete",
        "диабет",
        "глюкоза",
        "сахар",
        "сахар в крови",
    ],
    "sleep": [
        "sleep",
        "insomnia",
        "sleeping",
        "сон",
        "бессонница",
    ],
    "stress": [
        "stress",
        "burnout",
        "anxiety",
        "стресс",
        "выгорание",
        "тревога",
    ],
}


def _detect_red_flag_level(message: str) -> str:
    low = _normalize(message)
    for pattern in RED_FLAG_PATTERNS["emergency"]:
        if re.search(pattern, low):
            return "emergency"
    for pattern in RED_FLAG_PATTERNS["urgent"]:
        if re.search(pattern, low):
            return "urgent"
    return "none"


def _extract_symptom_summary(message: str) -> str:
    low = _normalize(message)
    parts: list[str] = []
    keywords = [
        "диабет",
        "сахар",
        "сон",
        "стресс",
        "боль",
        "глюкоза",
        "давление",
        "diabetes",
        "sugar",
        "sleep",
        "stress",
        "pain",
        "glucose",
        "blood glucose",
        "blood sugar",
        "pressure",
    ]
    matched = [keyword for keyword in keywords if keyword in low]
    if matched:
        parts.append("keywords=" + ", ".join(matched[:4]))
    duration_match = re.search(r"(?:\b\d+\s*(?:дн|дней|нед|weeks?|days?)\b)", low)
    if duration_match:
        parts.append("duration=" + duration_match.group(0))
    return "; ".join(parts) or message.strip()[:160]


def extract_patient_intake(message: str, prior: dict[str, Any] | None = None) -> PatientSymptomIntake:
    prior_model = PatientSymptomIntake.model_validate(prior or {})
    low = _normalize(message)
    symptoms = list(prior_model.symptoms)
    topics = list(prior_model.suspected_topics)

    symptom_keywords = [
        "боль",
        "одышка",
        "сахар",
        "сахар в крови",
        "глюкоза",
        "давление",
        "сон",
        "стресс",
        "pain",
        "shortness of breath",
        "sugar",
        "blood sugar",
        "glucose",
        "blood glucose",
        "pressure",
        "sleep",
        "stress",
    ]
    topic_keywords = {
        "diabetes": CONCEPT_SYNONYMS["diabetes"],
        "sleep": CONCEPT_SYNONYMS["sleep"],
        "stress": CONCEPT_SYNONYMS["stress"],
    }

    for keyword in symptom_keywords:
        if keyword in low and keyword not in symptoms:
            symptoms.append(keyword)
    for topic, keywords in topic_keywords.items():
        if any(keyword in low for keyword in keywords) and topic not in topics:
            topics.append(topic)

    duration = prior_model.duration
    duration_match = re.search(r"\b\d+\s*(?:дн(?:я|ей)?|нед(?:ел[яьи])?|weeks?|days?)\b", low)
    if duration_match:
        duration = duration_match.group(0)

    severity = prior_model.severity
    if any(token in low for token in ["сильн", "резк", "усилива", "severe", "intense", "worsen"]):
        severity = "severe"
    elif any(token in low for token in ["умерен", "moderate"]):
        severity = "moderate"
    elif any(token in low for token in ["легк", "mild"]):
        severity = "mild"

    summary = _extract_symptom_summary(message)
    if prior_model.summary and summary not in prior_model.summary:
        summary = prior_model.summary + " | " + summary

    return PatientSymptomIntake(
        summary=summary,
        symptoms=symptoms,
        suspected_topics=topics,
        duration=duration,
        severity=severity,
        free_text=message.strip()[:300],
    )


def _default_decision(message: str, state: dict[str, Any], language: str) -> PatientIntentDecision:
    current_mode = state.get("mode", "free_conversation")
    low = _normalize(message)
    red_flag_level = _detect_red_flag_level(message)
    if low in {"/start", "привет", "hello", "hi"}:
        return PatientIntentDecision(next_action="RESET_AND_GREET", confidence=0.98, rationale="greeting", red_flag_level="none", symptom_summary=None)
    if any(token in low for token in ["новый запрос", "по новому запросу", "давай новый запрос", "new request", "new concern", "something new"]):
        return PatientIntentDecision(next_action="RESET_TO_FREE", confidence=0.95, rationale="explicit new request", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
    if any(token in low for token in ["что умеешь", "what can you do", "capabilities"]):
        return PatientIntentDecision(next_action="SHOW_CAPABILITIES", confidence=0.95, rationale="capabilities", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
    if red_flag_level in {"urgent", "emergency"} and current_mode == "free_conversation":
        return PatientIntentDecision(next_action="RED_FLAG_GUIDANCE", confidence=0.93, rationale="red flag detected", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
    if current_mode == "awaiting_selection" and low.isdigit():
        return PatientIntentDecision(next_action="SELECT_CANDIDATE", confidence=0.95, rationale="candidate number selected", red_flag_level=red_flag_level, selected_candidate_index=int(low), symptom_summary=_extract_symptom_summary(message))
    if current_mode == "awaiting_consent":
        if low in {"да", "yes", "ok", "start", "давай"}:
            return PatientIntentDecision(next_action="START_ASSESSMENT", confidence=0.95, rationale="consent yes", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        if low in {"нет", "no", "later", "not now"}:
            return PatientIntentDecision(next_action="DECLINE", confidence=0.95, rationale="consent no", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        return PatientIntentDecision(next_action="RESTATE_CONSENT", confidence=0.72, rationale="consent ambiguous; restate current selection", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
    if current_mode == "assessment_in_progress":
        if low in {"пауза", "pause"}:
            return PatientIntentDecision(next_action="PAUSE", confidence=0.95, rationale="pause", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        if any(token in low for token in ["результат", "итог", "result", "summary"]):
            return PatientIntentDecision(next_action="SHOW_CURRENT_RESULT", confidence=0.9, rationale="current result request", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        if any(token in low for token in ["отчет", "отчёт", "report"]):
            return PatientIntentDecision(next_action="SHOW_CURRENT_REPORT", confidence=0.9, rationale="current report request", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        if any(token in low for token in ["объясни", "explain"]):
            return PatientIntentDecision(next_action="EXPLAIN_CURRENT_RESULT", confidence=0.9, rationale="explain current result", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        return PatientIntentDecision(next_action="RUN_RUNTIME_SUBGRAPH", confidence=0.85, rationale="assessment answer", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
    if current_mode == "paused_assessment":
        if low in {"продолжить", "resume", "continue", "дальше", "да"}:
            return PatientIntentDecision(next_action="RESUME", confidence=0.95, rationale="resume paused assessment", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        return PatientIntentDecision(next_action="SHOW_PAUSED", confidence=0.8, rationale="paused assessment", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
    if current_mode == "post_assessment":
        if any(token in low for token in ["результат", "итог", "result", "summary"]):
            return PatientIntentDecision(next_action="SHOW_LAST_RESULT", confidence=0.9, rationale="last result request", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        if any(token in low for token in ["отчет", "отчёт", "report"]):
            return PatientIntentDecision(next_action="SHOW_LAST_REPORT", confidence=0.9, rationale="last report request", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        if any(token in low for token in ["объясни", "explain"]):
            return PatientIntentDecision(next_action="EXPLAIN_LAST_RESULT", confidence=0.9, rationale="last explain request", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
        return PatientIntentDecision(next_action="SHOW_POST_OPTIONS", confidence=0.72, rationale="post-assessment ambiguous; keep context", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))
    return PatientIntentDecision(next_action="SEARCH", confidence=0.7, rationale="default search", red_flag_level=red_flag_level, symptom_summary=_extract_symptom_summary(message))


async def analyze_patient_turn(state: dict[str, Any]) -> PatientIntentDecision:
    message = str(state.get("user_message") or "")
    language = infer_turn_language(message, str(state.get("language") or detect_language(message)))
    payload = {
        "analysis_mode": "patient_turn",
        "language": language,
        "patient_message": message,
        "current_mode": state.get("mode", "free_conversation"),
        "consent_status": state.get("consent_status"),
        "candidate_count": len(state.get("candidates") or []),
        "symptom_summary": state.get("symptom_summary"),
    }
    raw = await controller_client().complete_json(
        system_prompt=(
            "Return strict JSON for patient routing. "
            "Allowed next_action values: RESET_AND_GREET, RESET_TO_FREE, SHOW_CAPABILITIES, RED_FLAG_GUIDANCE, SEARCH, SELECT_CANDIDATE, "
            "DECLINE, START_ASSESSMENT, PAUSE, RESUME, CANCEL, SHOW_PAUSED, SHOW_CURRENT_RESULT, SHOW_CURRENT_REPORT, "
            "EXPLAIN_CURRENT_RESULT, SHOW_LAST_RESULT, SHOW_LAST_REPORT, EXPLAIN_LAST_RESULT, RUN_RUNTIME_SUBGRAPH."
        ),
        user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
    )
    try:
        decision = PatientIntentDecision.model_validate(raw or {})
    except ValidationError:
        decision = _default_decision(message, state, language)
    if not decision.rationale:
        decision = _default_decision(message, state, language)
    detected_red_flag = _detect_red_flag_level(message)
    if decision.next_action == "RED_FLAG_GUIDANCE" and detected_red_flag == "none":
        decision = _default_decision(message, state, language)
    elif decision.red_flag_level != detected_red_flag:
        decision.red_flag_level = detected_red_flag
    return decision
