import re
from typing import Any

from fastapi import FastAPI

from shared.published_graph_store import load_active_graph_record
from shared.schemas import RuntimeMessageRequest, RuntimeMessageResponse

app = FastAPI(title="Runtime Agent", version="0.3.1")

SESSIONS: dict[str, dict[str, Any]] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "runtime-agent"}


def detect_language(text: str) -> str:
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "ru"
    return "en"


def _extract_runtime_graph(active_record: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(active_record, dict):
        return {"graph_id": None, "questions": [], "risk_bands": [], "scoring": {}}

    graph_id = active_record.get("graph_id")
    graph = active_record.get("graph", {})
    if not isinstance(graph, dict):
        graph = {}

    questions = graph.get("questions")
    risk_bands = graph.get("risk_bands")
    scoring = graph.get("scoring")

    if isinstance(questions, list):
        return {
            "graph_id": graph_id,
            "questions": questions,
            "risk_bands": risk_bands if isinstance(risk_bands, list) else [],
            "scoring": scoring if isinstance(scoring, dict) else {},
        }

    source_draft = graph.get("source_draft", {})
    if not isinstance(source_draft, dict):
        source_draft = {}

    return {
        "graph_id": graph_id,
        "questions": source_draft.get("candidate_questions", []) if isinstance(source_draft.get("candidate_questions"), list) else [],
        "risk_bands": source_draft.get("candidate_risk_bands", []) if isinstance(source_draft.get("candidate_risk_bands"), list) else [],
        "scoring": source_draft.get("candidate_scoring_rules", {}) if isinstance(source_draft.get("candidate_scoring_rules"), dict) else {},
    }


def _build_empty_session(conversation_id: str, graph_id: str | None, language: str) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "graph_id": graph_id,
        "language": language,
        "started": False,
        "current_question_index": 0,
        "awaiting_answer": False,
        "answers": [],
        "score_total": 0.0,
    }


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _pick_option(question: dict[str, Any], user_message: str) -> dict[str, Any] | None:
    options = question.get("options", [])
    if not isinstance(options, list) or not options:
        return None

    low = _normalize_text(user_message)

    if low.isdigit():
        idx = int(low) - 1
        if 0 <= idx < len(options):
            option = options[idx]
            return option if isinstance(option, dict) else None

    for option in options:
        if not isinstance(option, dict):
            continue
        label = option.get("label")
        if isinstance(label, str) and _normalize_text(label) == low:
            return option

    for option in options:
        if not isinstance(option, dict):
            continue
        label = option.get("label")
        if isinstance(label, str) and low in _normalize_text(label):
            return option

    return None


def _render_question(question: dict[str, Any], index: int, total: int, language: str) -> str:
    q_text = question.get("text", "Question")
    options = question.get("options", [])
    if not isinstance(options, list):
        options = []

    if language == "ru":
        parts = [f"Вопрос {index + 1}/{total}: {q_text}"]
        if options:
            parts.append("")
            parts.append("Варианты ответа:")
            for i, option in enumerate(options, start=1):
                if isinstance(option, dict):
                    parts.append(f"{i}. {option.get('label', '—')}")
            parts.append("")
            parts.append("Ответьте номером варианта или текстом варианта.")
        return "\n".join(parts)

    parts = [f"Question {index + 1}/{total}: {q_text}"]
    if options:
        parts.append("")
        parts.append("Answer options:")
        for i, option in enumerate(options, start=1):
            if isinstance(option, dict):
                parts.append(f"{i}. {option.get('label', '—')}")
        parts.append("")
        parts.append("Reply with the option number or the option text.")
    return "\n".join(parts)


def _find_risk_band(score_total: float, risk_bands: list[dict[str, Any]]) -> dict[str, Any] | None:
    for band in risk_bands:
        if not isinstance(band, dict):
            continue
        try:
            min_score = float(band.get("min_score"))
            max_score = float(band.get("max_score"))
        except Exception:
            continue
        if min_score <= score_total <= max_score:
            return band
    return None


def _build_completion_reply(language: str, score_total: float, risk_band: dict[str, Any] | None) -> str:
    if language == "ru":
        if risk_band:
            label = risk_band.get("label", "неизвестно")
            return (
                f"Спасибо. Assessment завершён.\n\n"
                f"Суммарный балл: {score_total:g}\n"
                f"Категория риска: {label}\n\n"
                f"Я подготавливаю summary."
            )
        return (
            f"Спасибо. Assessment завершён.\n\n"
            f"Суммарный балл: {score_total:g}\n\n"
            f"Я подготавливаю summary."
        )

    if risk_band:
        label = risk_band.get("label", "unknown")
        return (
            f"Thank you. The assessment is complete.\n\n"
            f"Total score: {score_total:g}\n"
            f"Risk category: {label}\n\n"
            f"I am preparing your summary."
        )
    return (
        f"Thank you. The assessment is complete.\n\n"
        f"Total score: {score_total:g}\n\n"
        f"I am preparing your summary."
    )


def _is_language_switch(message: str) -> str | None:
    low = _normalize_text(message)
    if "русск" in low or "говори по русски" in low or "говори по-русски" in low or low in {"на русском", "по-русски"}:
        return "ru"
    if "english" in low or "speak english" in low:
        return "en"
    return None


@app.post("/message", response_model=RuntimeMessageResponse)
async def process_user_message(payload: RuntimeMessageRequest) -> RuntimeMessageResponse:
    active_record = load_active_graph_record()
    runtime_graph = _extract_runtime_graph(active_record)
    questions = runtime_graph["questions"]
    risk_bands = runtime_graph["risk_bands"]

    if not questions:
        return RuntimeMessageResponse(
            conversation_id=payload.conversation_id,
            status="error",
            reply_text="No runnable questionnaire is published yet.",
            session_state={
                "conversation_id": payload.conversation_id,
                "active_graph_version_id": payload.active_graph_version_id,
                "answers": [],
                "score_total": 0.0,
            },
            should_generate_report=False,
        )

    session = SESSIONS.get(payload.conversation_id)
    if not session:
        session = _build_empty_session(
            conversation_id=payload.conversation_id,
            graph_id=runtime_graph["graph_id"],
            language=detect_language(payload.user_message),
        )
        SESSIONS[payload.conversation_id] = session

    maybe_lang = _is_language_switch(payload.user_message)
    if maybe_lang:
        session["language"] = maybe_lang

    language = session["language"]

    if not session["started"]:
        session["started"] = True
        session["awaiting_answer"] = True
        reply_text = _render_question(
            question=questions[session["current_question_index"]],
            index=session["current_question_index"],
            total=len(questions),
            language=language,
        )
        return RuntimeMessageResponse(
            conversation_id=payload.conversation_id,
            status="in_progress",
            reply_text=reply_text,
            session_state=session,
            should_generate_report=False,
        )

    current_index = session["current_question_index"]
    current_question = questions[current_index]
    chosen_option = _pick_option(current_question, payload.user_message)

    if current_question.get("options") and chosen_option is None:
        reply_text = _render_question(
            question=current_question,
            index=current_index,
            total=len(questions),
            language=language,
        )
        if language == "ru":
            reply_text = "Я не смог распознать вариант ответа.\n\n" + reply_text
        else:
            reply_text = "I could not match that answer to one of the options.\n\n" + reply_text

        return RuntimeMessageResponse(
            conversation_id=payload.conversation_id,
            status="in_progress",
            reply_text=reply_text,
            session_state=session,
            should_generate_report=False,
        )

    answer_record = {
        "question_id": current_question.get("id", f"q{current_index + 1}"),
        "question_text": current_question.get("text", ""),
        "raw_answer": payload.user_message,
        "selected_option": chosen_option.get("label") if isinstance(chosen_option, dict) else None,
        "score": float(chosen_option.get("score", 0)) if isinstance(chosen_option, dict) else 0.0,
    }
    session["answers"].append(answer_record)
    session["score_total"] += answer_record["score"]

    session["current_question_index"] += 1
    if session["current_question_index"] >= len(questions):
        risk_band = _find_risk_band(session["score_total"], risk_bands)
        reply_text = _build_completion_reply(language, session["score_total"], risk_band)
        final_session_state = {
            **session,
            "risk_band": risk_band,
            "active_graph_version_id": payload.active_graph_version_id,
        }
        return RuntimeMessageResponse(
            conversation_id=payload.conversation_id,
            status="completed",
            reply_text=reply_text,
            session_state=final_session_state,
            should_generate_report=True,
        )

    next_question = questions[session["current_question_index"]]
    reply_text = _render_question(
        question=next_question,
        index=session["current_question_index"],
        total=len(questions),
        language=language,
    )

    return RuntimeMessageResponse(
        conversation_id=payload.conversation_id,
        status="in_progress",
        reply_text=reply_text,
        session_state=session,
        should_generate_report=False,
    )
