import json
from typing import Any

from fastapi import FastAPI

from shared.config import get_settings
from shared.graph_registry import get_graph_record, list_graph_summaries, search_graphs
from shared.patient_graph_runtime import (
    answer_current_question,
    create_assessment_state,
    detect_language,
    explain_current_question,
    extract_runtime_graph,
    get_current_node,
    graph_meta,
    help_with_current_question,
    infer_answer_deterministically,
    repeat_current_question,
    start_assessment,
)
from shared.patient_session_store import load_session, save_session
from shared.together_client import TogetherAIClient

app = FastAPI(title="Patient Controller", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "patient-controller"}


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _detect_language_switch(message: str) -> str | None:
    low = _normalize(message)
    if "русск" in low or "на русском" in low or "по-русски" in low:
        return "ru"
    if "english" in low or "speak english" in low or "in english" in low:
        return "en"
    return None


def _is_greeting(message: str) -> bool:
    low = _normalize(message)
    return low in {"привет", "здравствуй", "здравствуйте", "hello", "hi", "hey"}


def _consent_from_message(message: str) -> str | None:
    low = _normalize(message)
    yes_words = {"да", "ок", "окей", "поехали", "начать", "давай", "хочу", "yes", "ok", "okay", "sure", "start", "let's start"}
    no_words = {"нет", "не хочу", "пока нет", "not now", "no", "later"}

    if low in yes_words:
        return "accepted"
    if low in no_words:
        return "declined"
    return None


def _looks_like_capabilities(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["что умеешь", "что ты умеешь", "что еще умеешь", "кроме", "what can you do", "what else can you do", "capabilities"])


def _looks_like_explain_assessment(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["что это", "что за тест", "что это за тест", "зачем этот тест", "what is this", "what is this test"])


def _looks_like_why_question(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["зачем этот вопрос", "почему этот вопрос", "why this question", "why do you ask"])


def _looks_like_help(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["не понял", "помоги", "help", "как отвечать", "не знаю", "что писать"])


def _looks_like_repeat(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["повтори", "ещё раз", "repeat", "again"])


def _looks_like_pause(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["пауза", "pause", "потом", "later", "останов", "stop for now"])


def _looks_like_resume(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["продолж", "resume", "continue", "дальше"])


def _looks_like_result_request(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["результат", "итог", "summary", "result"])


def _default_session(conversation_id: str, language: str) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "mode": "free_conversation",
        "language": language,
        "discovered_graphs": [],
        "selected_graph_id": None,
        "consent_status": None,
        "assessment_state": None,
        "last_result": None,
        "history": [],
    }


def _capabilities_text(language: str) -> str:
    graphs = list_graph_summaries(limit=8)
    if not graphs:
        return (
            "Сейчас в библиотеке графов пока нет опубликованных assessments."
            if language == "ru"
            else "There are no published assessments in the graph library yet."
        )

    lines = []
    if language == "ru":
        lines.append("Я могу помочь подобрать и провести assessment из доступной библиотеки графов.")
        lines.append("")
        lines.append("Сейчас доступны такие assessments:")
        for item in graphs[:5]:
            lines.append(
                f"- {item.get('title')} ({item.get('questions_count', '?')} вопросов, ~{item.get('estimated_time_minutes', '?')} мин)"
            )
        lines.append("")
        lines.append("Если опишете свой запрос, цель или проблему, я постараюсь подобрать наиболее подходящий assessment.")
    else:
        lines.append("I can help choose and run an assessment from the available graph library.")
        lines.append("")
        lines.append("Right now these assessments are available:")
        for item in graphs[:5]:
            lines.append(
                f"- {item.get('title')} ({item.get('questions_count', '?')} questions, ~{item.get('estimated_time_minutes', '?')} min)"
            )
        lines.append("")
        lines.append("If you describe your concern, goal, or problem, I will try to find the most relevant assessment.")

    return "\n".join(lines)


def _greeting_text(language: str) -> str:
    if language == "ru":
        return (
            "Привет. Я могу пообщаться с вами в свободной форме, помочь разобраться с запросом и, если это уместно, подобрать assessment из моей библиотеки.\n\n"
            "Можете просто рассказать, что вас беспокоит или что вы хотите оценить."
        )
    return (
        "Hi. I can talk with you freely, help understand your request, and, when relevant, select an assessment from my library.\n\n"
        "You can simply describe what is bothering you or what you would like to evaluate."
    )


def _offer_text(candidate: dict[str, Any], language: str) -> str:
    metadata = candidate.get("metadata", {}) or {}
    title = metadata.get("title") or candidate.get("graph_id")
    description = metadata.get("description") or ""
    questions_count = metadata.get("questions_count") or "?"
    duration = metadata.get("estimated_time_minutes") or "?"

    if language == "ru":
        return (
            f"По вашему описанию вам может подойти assessment «{title}».\n"
            f"{description}\n"
            f"Это примерно {questions_count} вопросов и около {duration} минут.\n\n"
            f"Хотите пройти его сейчас?"
        )
    return (
        f"Based on what you described, a suitable assessment may be “{title}”.\n"
        f"{description}\n"
        f"It is about {questions_count} questions and around {duration} minutes.\n\n"
        f"Would you like to take it now?"
    )


def _no_match_text(language: str) -> str:
    if language == "ru":
        return (
            "Я пока не нашёл явно подходящий assessment по этому описанию.\n"
            "Можете рассказать чуть подробнее, что именно вы хотите оценить, или спросить, какие assessments сейчас доступны."
        )
    return (
        "I have not found a clearly suitable assessment for that description yet.\n"
        "You can tell me a bit more about what you want to evaluate, or ask which assessments are currently available."
    )


def _decline_text(language: str) -> str:
    if language == "ru":
        return "Хорошо, не будем запускать assessment сейчас. Можете продолжать свободный диалог, и я помогу подобрать другой вариант, если нужно."
    return "Okay, we do not have to start the assessment right now. You can continue the conversation freely, and I can help find another option if needed."


def _result_text(result: dict[str, Any] | None, language: str) -> str:
    if not isinstance(result, dict):
        return (
            "Assessment ещё не завершён. Если хотите, можем продолжить."
            if language == "ru"
            else "The assessment is not completed yet. If you want, we can continue."
        )

    risk_band = result.get("risk_band") or {}
    if language == "ru":
        return (
            f"Тема: {result.get('graph_title')}\n"
            f"Суммарный балл: {result.get('score_total')}\n"
            f"Категория: {risk_band.get('label', '—')}"
        )
    return (
        f"Topic: {result.get('graph_title')}\n"
        f"Total score: {result.get('score_total')}\n"
        f"Category: {risk_band.get('label', '—')}"
    )


async def _llm_map_answer(node: dict[str, Any], message: str, language: str) -> dict[str, Any]:
    settings = get_settings()
    llm = TogetherAIClient(model=settings.patient_controller_model)

    system_prompt = (
        "You are an answer normalizer for a conversational assessment assistant.\n"
        "Map the user's free-form answer to the current graph node.\n\n"
        "Return only valid JSON with keys:\n"
        "- ok\n"
        "- value\n"
        "- selected_option\n"
        "- score\n\n"
        "If the answer cannot be mapped safely, return {\"ok\": false}.\n"
    )

    user_prompt = json.dumps(
        {
            "language": language,
            "node": {
                "id": node.get("id"),
                "question_type": node.get("question_type"),
                "text": node.get("text"),
                "help_text": node.get("help_text"),
                "options": node.get("options"),
                "normalization_rule": node.get("normalization_rule"),
                "validation_rule": node.get("validation_rule"),
            },
            "user_reply": message,
        },
        ensure_ascii=False,
        indent=2,
    )

    try:
        result = await llm.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
    except Exception:
        result = None

    if not isinstance(result, dict):
        return {"ok": False, "raw_answer": message}

    if not result.get("ok"):
        return {"ok": False, "raw_answer": message}

    try:
        score = float(result.get("score", 0.0))
    except Exception:
        score = 0.0

    selected_option = result.get("selected_option")
    return {
        "ok": True,
        "raw_answer": message,
        "value": result.get("value"),
        "selected_option": selected_option if isinstance(selected_option, str) else None,
        "score": score,
    }


async def _find_graph_candidates(message: str, language: str) -> list[dict[str, Any]]:
    candidates = search_graphs(message, top_k=5)
    return candidates


@app.post("/chat")
async def chat(payload: dict[str, Any]) -> dict[str, Any]:
    conversation_id = str(payload.get("conversation_id") or "unknown_conversation")
    user_message = str(payload.get("user_message") or "").strip()

    if not user_message:
        return {"status": "error", "reply_text": "Empty message", "session_state": {}}

    session = load_session(conversation_id)
    if not isinstance(session, dict):
        session = _default_session(conversation_id, detect_language(user_message))

    maybe_lang = _detect_language_switch(user_message)
    if maybe_lang:
        session["language"] = maybe_lang
    language = session["language"]

    mode = session.get("mode", "free_conversation")
    reply_text = ""

    if user_message == "/start":
        reply_text = _greeting_text(language)

    elif _looks_like_capabilities(user_message):
        reply_text = _capabilities_text(language)

    elif mode == "awaiting_consent":
        consent = _consent_from_message(user_message)
        if consent == "accepted":
            graph_id = session.get("selected_graph_id")
            record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
            runtime_graph = extract_runtime_graph(record)
            assessment_state = create_assessment_state(runtime_graph, language)
            rendered = start_assessment(runtime_graph, assessment_state)
            session["assessment_state"] = rendered["assessment_state"]
            session["mode"] = "assessment_in_progress"
            session["consent_status"] = "accepted"
            reply_text = rendered["reply_text"]
        elif consent == "declined":
            session["mode"] = "free_conversation"
            session["consent_status"] = "declined"
            session["selected_graph_id"] = None
            reply_text = _decline_text(language)
        else:
            graph_id = session.get("selected_graph_id")
            record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
            if record:
                reply_text = _offer_text(
                    {
                        "graph_id": record.get("graph_id"),
                        "metadata": record.get("metadata", {}),
                    },
                    language,
                )
            else:
                session["mode"] = "free_conversation"
                reply_text = _no_match_text(language)

    elif mode == "assessment_in_progress":
        graph_id = session.get("selected_graph_id")
        record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
        runtime_graph = extract_runtime_graph(record)
        assessment_state = session.get("assessment_state")
        if not isinstance(assessment_state, dict):
            assessment_state = create_assessment_state(runtime_graph, language)
            session["assessment_state"] = assessment_state

        if _looks_like_pause(user_message):
            session["mode"] = "paused_assessment"
            reply_text = (
                "Хорошо, поставим assessment на паузу. Когда захотите продолжить, просто напишите мне."
                if language == "ru"
                else "Okay, we can pause the assessment here. When you want to continue, just send me a message."
            )
        elif maybe_lang:
            assessment_state["language"] = language
            session["assessment_state"] = assessment_state
            ack = "Хорошо, продолжим по-русски.\n\n" if language == "ru" else "Okay, we will continue in English.\n\n"
            reply_text = ack + repeat_current_question(runtime_graph, assessment_state)
        elif _is_greeting(user_message):
            reply_text = (
                "Привет. Мы сейчас находимся внутри assessment. Если хотите, можем продолжить с текущего вопроса.\n\n"
                + repeat_current_question(runtime_graph, assessment_state)
                if language == "ru"
                else "Hi. We are currently inside the assessment. If you want, we can continue from the current question.\n\n"
                + repeat_current_question(runtime_graph, assessment_state)
            )
        elif _looks_like_why_question(user_message):
            reply_text = explain_current_question(runtime_graph, assessment_state) + "\n\n" + repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_help(user_message):
            reply_text = help_with_current_question(runtime_graph, assessment_state) + "\n\n" + repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_repeat(user_message):
            reply_text = repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_result_request(user_message):
            reply_text = _result_text(assessment_state.get("result"), language)
        elif _looks_like_capabilities(user_message):
            reply_text = (
                "Сейчас мы проходим один assessment. Я могу продолжить его, поставить на паузу или позже помочь подобрать другой graph."
                if language == "ru"
                else "We are currently going through one assessment. I can continue it, pause it, or later help choose another graph."
            )
        else:
            node = get_current_node(runtime_graph, assessment_state)
            deterministic = infer_answer_deterministically(node or {}, user_message, language)
            normalized = deterministic
            if not deterministic.get("ok") and isinstance(node, dict):
                normalized = await _llm_map_answer(node, user_message, language)
            result = answer_current_question(runtime_graph, assessment_state, normalized)
            session["assessment_state"] = result["assessment_state"]
            reply_text = result["reply_text"]
            if result.get("completed"):
                session["mode"] = "post_assessment"
                session["last_result"] = (result["assessment_state"] or {}).get("result")

    elif mode == "paused_assessment":
        if _looks_like_resume(user_message) or _consent_from_message(user_message) == "accepted":
            session["mode"] = "assessment_in_progress"
            graph_id = session.get("selected_graph_id")
            record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
            runtime_graph = extract_runtime_graph(record)
            assessment_state = session.get("assessment_state")
            if not isinstance(assessment_state, dict):
                assessment_state = create_assessment_state(runtime_graph, language)
                session["assessment_state"] = assessment_state
            assessment_state["language"] = language
            reply_text = repeat_current_question(runtime_graph, assessment_state)
        else:
            reply_text = (
                "Сейчас assessment на паузе. Когда захотите продолжить, просто скажите об этом."
                if language == "ru"
                else "The assessment is currently paused. When you want to continue, just tell me."
            )

    else:
        if _looks_like_result_request(user_message):
            reply_text = _result_text(session.get("last_result"), language)
        elif _looks_like_explain_assessment(user_message):
            reply_text = (
                "Я могу помочь подобрать assessment из библиотеки графов, предложить наиболее подходящий вариант и провести вас по нему шаг за шагом."
                if language == "ru"
                else "I can help select an assessment from the graph library, suggest the most relevant option, and guide you through it step by step."
            )
        elif _is_greeting(user_message):
            reply_text = _greeting_text(language)
        else:
            candidates = await _find_graph_candidates(user_message, language)
            if candidates:
                top = candidates[0]
                if float(top.get("score", 0.0)) >= 3.0:
                    session["mode"] = "awaiting_consent"
                    session["selected_graph_id"] = top.get("graph_id")
                    session["discovered_graphs"] = [c.get("graph_id") for c in candidates if c.get("graph_id")]
                    session["consent_status"] = "pending"
                    reply_text = _offer_text(top, language)
                else:
                    reply_text = _no_match_text(language)
            else:
                reply_text = _no_match_text(language)

    history = session.get("history", [])
    if not isinstance(history, list):
        history = []
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply_text})
    session["history"] = history[-20:]
    save_session(conversation_id, session)

    return {
        "status": session.get("mode", "free_conversation"),
        "reply_text": reply_text,
        "session_state": session,
    }
