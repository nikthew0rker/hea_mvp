import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from shared.config import get_settings
from shared.input_normalizer import normalize_specialist_input
from shared.prompt_loader import load_json_file
from shared.schemas import DraftRequest, DraftResponse
from shared.together_client import TogetherAIClient

app = FastAPI(title="Definition Agent", version="0.4.0")

BASE_DIR = Path(__file__).resolve().parents[2]
POLICY_PATH = BASE_DIR / "config" / "definition_agent_policy.json"


@app.get("/health")
async def health() -> dict:
    """
    Healthcheck endpoint for the Definition Agent.
    """
    return {"status": "ok", "service": "definition-agent"}


@app.post("/draft", response_model=DraftResponse)
async def build_draft(payload: DraftRequest) -> DraftResponse:
    """
    Update or edit the current structured draft.

    This implementation is hardened against malformed LLM JSON and supports:
    - update mode for new medical content
    - edit mode for natural-language changes over the current draft
    """
    policy = load_json_file(str(POLICY_PATH))
    current_draft = payload.current_draft or {}
    language = payload.current_language or "ru"

    if payload.operation == "edit":
        merged = await _apply_edit_instruction(
            policy=policy,
            instruction=payload.specialist_text,
            current_draft=current_draft,
            language=language,
        )
        merged["conversation_id"] = payload.conversation_id
        return DraftResponse(**merged)

    normalized = normalize_specialist_input(payload.specialist_text)

    llm_candidate = await _extract_with_llm(
        policy=policy,
        normalized=normalized,
        current_draft=current_draft,
        conversation_summary=payload.conversation_summary,
    )

    merged = merge_draft_state(
        current_draft=current_draft,
        heuristic=normalized["heuristic_candidates"],
        llm_candidate=llm_candidate,
        language=normalized["language"],
    )
    merged["conversation_id"] = payload.conversation_id
    return DraftResponse(**merged)


async def _extract_with_llm(
    *,
    policy: dict[str, Any],
    normalized: dict[str, Any],
    current_draft: dict[str, Any],
    conversation_summary: str | None,
) -> dict[str, Any]:
    """
    Extract assessment structure from normalized specialist input.
    """
    settings = get_settings()
    llm = TogetherAIClient(model=settings.definition_agent_model)

    system_prompt = (
        "You are a medical assessment definition extraction agent.\n"
        "Convert specialist messages, pasted scales, checklists, tables, and noisy document fragments "
        "into structured assessment definition state.\n\n"
        f"Policy:\n{json.dumps(policy, ensure_ascii=False, indent=2)}\n\n"
        "Return only valid JSON with keys:\n"
        "language, understood, candidate_questions, candidate_scoring_rules, candidate_risk_bands, "
        "candidate_report_requirements, candidate_safety_requirements, missing_fields, suggested_next_question, status.\n\n"
        "Rules:\n"
        "- if the input already contains questions, extract them\n"
        "- if the input contains score thresholds, extract risk bands\n"
        "- if the input contains recommendations or follow-up logic, place them into report or safety candidates\n"
        "- prefer extraction over generic clarification\n"
        "- do not produce conversational text\n"
        "- do not produce markdown\n"
    )

    user_prompt = json.dumps(
        {
            "conversation_summary": conversation_summary,
            "normalized_input": normalized,
            "current_draft": current_draft,
        },
        ensure_ascii=False,
        indent=2,
    )

    result = await llm.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
    return _sanitize_llm_candidate(result)


async def _apply_edit_instruction(
    *,
    policy: dict[str, Any],
    instruction: str,
    current_draft: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """
    Apply a natural-language edit instruction to the current draft.
    """
    settings = get_settings()
    llm = TogetherAIClient(model=settings.definition_agent_model)

    system_prompt = (
        "You are a definition editor agent.\n"
        "You receive an existing structured assessment draft and a specialist edit instruction.\n"
        "Apply the edit conservatively and return only valid JSON.\n\n"
        f"Policy:\n{json.dumps(policy, ensure_ascii=False, indent=2)}\n\n"
        "Return JSON with keys:\n"
        "language, understood, candidate_questions, candidate_scoring_rules, candidate_risk_bands, "
        "candidate_report_requirements, candidate_safety_requirements, missing_fields, suggested_next_question, status.\n\n"
        "Rules:\n"
        "- preserve all existing information that was not explicitly changed\n"
        "- if the instruction is ambiguous, keep the draft and ask for one clarification question\n"
        "- do not output conversational text\n"
    )

    user_prompt = json.dumps(
        {
            "instruction": instruction,
            "current_draft": current_draft,
            "language": language,
        },
        ensure_ascii=False,
        indent=2,
    )

    result = await llm.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
    llm_candidate = _sanitize_llm_candidate(result)

    return merge_draft_state(
        current_draft=current_draft,
        heuristic={},
        llm_candidate=llm_candidate,
        language=language,
    )


def _ensure_dict(value: Any) -> dict[str, Any]:
    """
    Return a dict if the value is a dict, otherwise an empty dict.
    """
    return value if isinstance(value, dict) else {}


def _ensure_list(value: Any) -> list[Any]:
    """
    Return a list if the value is a list, otherwise an empty list.
    """
    return value if isinstance(value, list) else []


def _ensure_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    """
    Keep only dict items from a list-like value.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _ensure_string_list(value: Any) -> list[str]:
    """
    Keep only string items from a list-like value.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _sanitize_llm_candidate(candidate: dict | None) -> dict[str, Any]:
    """
    Normalize model output into the shapes expected by merge logic.
    """
    candidate = candidate if isinstance(candidate, dict) else {}

    suggested_next_question = candidate.get("suggested_next_question")
    status = candidate.get("status")
    language = candidate.get("language")

    return {
        "understood": _ensure_dict(candidate.get("understood")),
        "candidate_questions": _ensure_list_of_dicts(candidate.get("candidate_questions")),
        "candidate_scoring_rules": _ensure_dict(candidate.get("candidate_scoring_rules")),
        "candidate_risk_bands": _ensure_list_of_dicts(candidate.get("candidate_risk_bands")),
        "candidate_report_requirements": _ensure_list_of_dicts(candidate.get("candidate_report_requirements")),
        "candidate_safety_requirements": _ensure_list_of_dicts(candidate.get("candidate_safety_requirements")),
        "missing_fields": _ensure_string_list(candidate.get("missing_fields")),
        "suggested_next_question": suggested_next_question if isinstance(suggested_next_question, str) else None,
        "status": status if isinstance(status, str) else None,
        "language": language if isinstance(language, str) else None
    }


def merge_draft_state(
    *,
    current_draft: dict[str, Any],
    heuristic: dict[str, Any],
    llm_candidate: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """
    Merge current draft state, heuristics, and sanitized LLM extraction into one draft.

    Priority:
    1. explicit new LLM content
    2. existing current draft
    3. heuristic fallback
    """
    current_draft = _ensure_dict(current_draft)
    heuristic = _ensure_dict(heuristic)
    llm_candidate = _sanitize_llm_candidate(llm_candidate)

    understood_current = _ensure_dict(current_draft.get("understood"))
    understood_llm = _ensure_dict(llm_candidate.get("understood"))

    topic = understood_llm.get("topic") or understood_current.get("topic") or heuristic.get("topic")
    target_audience = understood_llm.get("target_audience") or understood_current.get("target_audience")

    questions = _merge_questions(
        _ensure_list_of_dicts(current_draft.get("candidate_questions")),
        _ensure_list_of_dicts(llm_candidate.get("candidate_questions")),
        _ensure_list_of_dicts(heuristic.get("questions"))
    )

    scoring_rules = (
        _ensure_dict(llm_candidate.get("candidate_scoring_rules"))
        or _ensure_dict(current_draft.get("candidate_scoring_rules"))
        or _ensure_dict(heuristic.get("scoring_logic"))
    )

    risk_bands = _merge_risk_bands(
        _ensure_list_of_dicts(current_draft.get("candidate_risk_bands")),
        _ensure_list_of_dicts(llm_candidate.get("candidate_risk_bands")),
        _ensure_list_of_dicts(heuristic.get("risk_bands"))
    )

    report_requirements = _merge_generic(
        _ensure_list_of_dicts(current_draft.get("candidate_report_requirements")),
        _ensure_list_of_dicts(llm_candidate.get("candidate_report_requirements"))
    )

    safety_requirements = _merge_generic(
        _ensure_list_of_dicts(current_draft.get("candidate_safety_requirements")),
        _ensure_list_of_dicts(llm_candidate.get("candidate_safety_requirements"))
    )

    understood = {
        "topic": topic,
        "target_audience": target_audience,
        "questions_count": len(questions)
    }

    missing_fields = []
    if not topic:
        missing_fields.append("topic")
    if len(questions) == 0:
        missing_fields.append("questions")
    if not scoring_rules or not scoring_rules.get("method"):
        missing_fields.append("scoring_logic")
    if len(risk_bands) == 0:
        missing_fields.append("risk_bands")

    blocking = {"topic", "questions", "scoring_logic"}
    status = "ready_to_compile" if not any(x in blocking for x in missing_fields) else "needs_clarification"

    next_question = (
        llm_candidate.get("suggested_next_question")
        if status == "needs_clarification" and llm_candidate.get("suggested_next_question")
        else build_next_question(missing_fields, language)
    )

    draft = {
        "language": language,
        "understood": understood,
        "candidate_questions": questions,
        "candidate_scoring_rules": scoring_rules,
        "candidate_risk_bands": risk_bands,
        "candidate_report_requirements": report_requirements,
        "candidate_safety_requirements": safety_requirements,
        "missing_fields": missing_fields
    }

    return {
        "status": status,
        "language": language,
        "understood": understood,
        "candidate_questions": questions,
        "candidate_scoring_rules": scoring_rules,
        "candidate_risk_bands": risk_bands,
        "candidate_report_requirements": report_requirements,
        "candidate_safety_requirements": safety_requirements,
        "missing_fields": missing_fields,
        "suggested_next_question": next_question,
        "draft": draft
    }


def build_next_question(missing_fields: list[str], language: str) -> str | None:
    """
    Build one useful next clarification question.
    """
    if not missing_fields:
        return None

    first = missing_fields[0]

    ru = {
        "topic": "Какой именно health risk, состояние или проблему должен оценивать этот ассессмент?",
        "questions": "Какие именно вопросы ты хочешь задавать пользователю?",
        "scoring_logic": "Как должна считаться итоговая оценка: сумма баллов, веса, ветвление или другое правило?",
        "risk_bands": "Есть ли диапазоны итогового риска или уровни интерпретации результата?"
    }

    en = {
        "topic": "What exact health risk, condition, or problem should this assessment evaluate?",
        "questions": "Which exact questions do you want to ask the user?",
        "scoring_logic": "How should the final score be calculated: sum of points, weights, branching, or another rule?",
        "risk_bands": "Are there final risk bands or interpretation levels for the result?"
    }

    return ru.get(first) if language == "ru" else en.get(first)


def _merge_questions(*sources: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """
    Merge question candidates while deduplicating by id and text.
    """
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()

    for source in sources:
        if not source:
            continue

        for item in source:
            if not isinstance(item, dict):
                continue

            qid = str(item.get("id", "")).strip()
            text = str(item.get("text", "")).strip()

            if not text:
                continue

            text_key = text.lower()

            if qid and qid in seen_ids:
                continue

            if text_key in seen_texts:
                continue

            if not qid:
                qid = f"q{len(merged) + 1}"

            normalized = {
                "id": qid,
                "text": text,
                "question_type": item.get("question_type", "single_choice"),
                "options": _ensure_list(item.get("options")),
                "notes": item.get("notes")
            }

            merged.append(normalized)
            seen_ids.add(qid)
            seen_texts.add(text_key)

    return merged


def _merge_risk_bands(*sources: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """
    Merge risk-band candidates while deduplicating by score range and label.
    """
    merged: list[dict[str, Any]] = []
    seen: set[tuple[float, float, str]] = set()

    for source in sources:
        if not source:
            continue

        for item in source:
            if not isinstance(item, dict):
                continue

            try:
                key = (
                    float(item["min_score"]),
                    float(item["max_score"]),
                    str(item["label"]).strip().lower()
                )
            except Exception:
                continue

            if key in seen:
                continue

            merged.append(
                {
                    "min_score": key[0],
                    "max_score": key[1],
                    "label": item["label"],
                    "meaning": item.get("meaning")
                }
            )
            seen.add(key)

    return merged


def _merge_generic(*sources: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """
    Merge generic requirement lists with text-based deduplication.
    """
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source in sources:
        if not source:
            continue

        for item in source:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title", "")).strip()
            instruction = str(item.get("instruction", "")).strip()

            if not title and not instruction:
                continue

            key = f"{title.lower()}::{instruction.lower()}"
            if key in seen:
                continue

            merged.append({"title": title, "instruction": instruction})
            seen.add(key)

    return merged
