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
    explain_last_result,
    extract_runtime_graph,
    get_current_node,
    help_with_current_question,
    infer_answer_deterministically,
    repeat_current_question,
    start_assessment,
)
from shared.patient_session_store import load_session, save_session
from shared.together_client import TogetherAIClient

app = FastAPI(title="Patient Controller", version="1.1.2")


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


def _looks_like_acknowledgement(message: str) -> bool:
    low = _normalize(message)
    return low in {
        "ок", "окей", "понял", "понятно", "хорошо", "отлично", "ясно",
        "ok", "okay", "got it", "understood", "great", "fine",
    }


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
    return any(token in low for token in ["пауза", "pause", "потом", "later"])


def _looks_like_resume(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["продолж", "resume", "continue", "дальше"])


def _looks_like_cancel(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["отмена", "стоп", "cancel", "stop", "не хочу продолжать", "хватит"])


def _looks_like_result_request(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["результат", "итог", "summary", "result", "дай результат"])


def _looks_like_explain_last_result(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["объясни", "обьясни", "что это значит", "explain", "what does it mean"])


def _looks_like_detailed_report(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in [
        "подробный отчет",
        "подробный отчёт",
        "полный отчет",
        "полный отчёт",
        "детальный отчет",
        "детальный отчёт",
        "detailed report",
        "full report",
        "report",
    ])


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


def _capabilities_text(language: str, in_assessment: bool = False) -> str:
    graphs = list_graph_summaries(limit=8)

    if in_assessment:
        if language == "ru":
            return (
                "Сейчас мы находимся внутри assessment.\n"
                "Я могу:\n"
                "- принять ваш ответ,\n"
                "- повторить вопрос,\n"
                "- объяснить, зачем он нужен,\n"
                "- помочь с форматом ответа,\n"
                "- поставить assessment на паузу,\n"
                "- остановить его полностью.\n\n"
                "После завершения я также могу помочь подобрать другой assessment."
            )
        return (
            "We are currently inside an assessment.\n"
            "I can:\n"
            "- accept your answer,\n"
            "- repeat the question,\n"
            "- explain why it matters,\n"
            "- help with the answer format,\n"
            "- pause the assessment,\n"
            "- stop it completely.\n\n"
            "After completion I can also help choose another assessment."
        )

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


def _detailed_report_text(last_result: dict[str, Any] | None, language: str) -> str:
    if not isinstance(last_result, dict):
        return (
            "Сейчас у меня нет завершённого результата для подробного отчёта."
            if language == "ru"
            else "I do not have a completed result for a detailed report right now."
        )

    graph_title = last_result.get("graph_title", "assessment")
    score_total = last_result.get("score_total", "—")
    risk_band = last_result.get("risk_band") or {}
    label = risk_band.get("label", "—")
    meaning = risk_band.get("meaning")

    if language == "ru":
        lines = [
            f"Подробный отчёт по assessment «{graph_title}»:",
            "",
            f"- Итоговый балл: {score_total}",
            f"- Категория результата: {label}",
        ]
        if meaning:
            lines.append(f"- Интерпретация по логике graph: {meaning}")
        lines.extend([
            "",
            "Это screening assessment result, а не диагноз.",
            "Если хотите, я могу помочь подобрать другой assessment по новому запросу.",
        ])
        return "\n".join(lines)

    lines = [
        f"Detailed report for the assessment “{graph_title}”:",
        "",
        f"- Total score: {score_total}",
        f"- Result category: {label}",
    ]
    if meaning:
        lines.append(f"- Graph interpretation: {meaning}")
    lines.extend([
        "",
        "This is a screening assessment result, not a diagnosis.",
        "If you want, I can help choose another assessment for a new concern.",
    ])
    return "\n".join(lines)


async def _llm_map_answer(node: dict[str, Any], message: str, language: str) -> dict[str, Any]:
    settings = get_settings()
    llm = TogetherAIClient(model=settings.patient_controller_model)

    system_prompt = (
        "You are an answer normalizer for a conversational assessment assistant.\n"
        "Map the user's free-form answer to the current graph node.\n\n"
        "Return only valid JSON with keys:\n"
        "- status\n"
        "- value\n"
        "- selected_option\n"
        "- score\n\n"
        "Allowed status values:\n"
        "- full_match\n"
        "- no_match\n\n"
        "If the answer cannot be mapped safely, return status=no_match.\n"
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
        return {"status": "no_match", "raw_answer": message}

    if result.get("status") != "full_match":
        return {"status": "no_match", "raw_answer": message}

    try:
        score = float(result.get("score", 0.0))
    except Exception:
        score = 0.0

    selected_option = result.get("selected_option")
    return {
        "status": "full_match",
        "raw_answer": message,
        "value": result.get("value"),
        "selected_option": selected_option if isinstance(selected_option, str) else None,
        "score": score,
    }


async def _find_graph_candidates(message: str, language: str) -> list[dict[str, Any]]:
    return search_graphs(message, top_k=5)


@app.post("/chat")
async def chat(payload: dict[str, Any]) -> dict[str, Any]:
    conversation_id = str(payload.get("conversation_id") or "unknown_conversation")
    user_message = str(payload.get("user_message") or "").strip()

    if not user_message:
        return {"status": "error", "reply_text": "Empty message", "session_state": {}}

    existing_session = load_session(conversation_id)
    if not isinstance(existing_session, dict):
        existing_session = _default_session(conversation_id, detect_language(user_message))

    maybe_lang = _detect_language_switch(user_message)
    base_language = maybe_lang or existing_session.get("language") or detect_language(user_message)

    if user_message == "/start":
        session = _default_session(conversation_id, base_language)
        reply_text = _greeting_text(base_language)
        history = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply_text},
        ]
        session["history"] = history
        save_session(conversation_id, session)
        return {
            "status": session.get("mode", "free_conversation"),
            "reply_text": reply_text,
            "session_state": session,
        }

    session = existing_session
    if maybe_lang:
        session["language"] = maybe_lang
    language = session["language"]

    mode = session.get("mode", "free_conversation")
    reply_text = ""

    if _looks_like_capabilities(user_message):
        reply_text = _capabilities_text(language, in_assessment=(mode == "assessment_in_progress"))

    elif _looks_like_cancel(user_message):
        if mode in {"assessment_in_progress", "paused_assessment"}:
            session["mode"] = "free_conversation"
            session["assessment_state"] = None
            session["selected_graph_id"] = None
            session["consent_status"] = None
            reply_text = (
                "Хорошо, я остановил текущий assessment. Можем вернуться к свободному диалогу и подобрать другой вариант, если нужно."
                if language == "ru"
                else "Okay, I stopped the current assessment. We can return to free conversation and choose another option if needed."
            )
        else:
            reply_text = (
                "Сейчас нет активного assessment для отмены."
                if language == "ru"
                else "There is no active assessment to cancel right now."
            )

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
        elif _looks_like_explain_assessment(user_message):
            graph_id = session.get("selected_graph_id")
            record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
            if isinstance(record, dict):
                candidate = {"graph_id": record.get("graph_id"), "metadata": record.get("metadata", {})}
                reply_text = _offer_text(candidate, language)
            else:
                session["mode"] = "free_conversation"
                reply_text = _no_match_text(language)
        else:
            candidates = await _find_graph_candidates(user_message, language)
            if candidates and float(candidates[0].get("score", 0.0)) >= 3.0:
                top = candidates[0]
                session["selected_graph_id"] = top.get("graph_id")
                session["discovered_graphs"] = [c.get("graph_id") for c in candidates if c.get("graph_id")]
                session["consent_status"] = "pending"
                reply_text = _offer_text(top, language)
            else:
                graph_id = session.get("selected_graph_id")
                record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
                if isinstance(record, dict):
                    reply_text = _offer_text({"graph_id": record.get("graph_id"), "metadata": record.get("metadata", {})}, language)
                else:
                    reply_text = _no_match_text(language)

    elif mode == "assessment_in_progress":
        graph_id = session.get("selected_graph_id")
        record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
        runtime_graph = extract_runtime_graph(record)

        assessment_state = session.get("assessment_state")
        if not isinstance(assessment_state, dict):
            assessment_state = create_assessment_state(runtime_graph, language)
            session["assessment_state"] = assessment_state

        assessment_state["language"] = language
        session["assessment_state"] = assessment_state

        if _looks_like_pause(user_message):
            session["mode"] = "paused_assessment"
            reply_text = (
                "Хорошо, поставим assessment на паузу. Когда захотите продолжить, просто напишите мне."
                if language == "ru"
                else "Okay, we can pause the assessment here. When you want to continue, just send me a message."
            )
        elif maybe_lang:
            reply_text = ("Хорошо, продолжим по-русски.\n\n" if language == "ru" else "Okay, we will continue in English.\n\n") + repeat_current_question(runtime_graph, assessment_state)
        elif _is_greeting(user_message):
            reply_text = (
                "Привет. Мы сейчас внутри assessment. Если хотите, можем продолжить с текущего вопроса.\n\n"
                if language == "ru"
                else "Hi. We are currently inside the assessment. If you want, we can continue from the current question.\n\n"
            ) + repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_why_question(user_message):
            reply_text = explain_current_question(runtime_graph, assessment_state) + "\n\n" + repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_help(user_message):
            reply_text = help_with_current_question(runtime_graph, assessment_state) + "\n\n" + repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_repeat(user_message):
            reply_text = repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_result_request(user_message):
            reply_text = _result_text(assessment_state.get("result"), language)
        elif _looks_like_detailed_report(user_message):
            reply_text = _detailed_report_text(assessment_state.get("result"), language)
        elif _looks_like_explain_last_result(user_message):
            if assessment_state.get("result"):
                reply_text = explain_last_result(assessment_state.get("result"), language)
            else:
                reply_text = (
                    "Сначала нужно завершить assessment, и тогда я смогу объяснить результат."
                    if language == "ru"
                    else "The assessment needs to be completed first, and then I can explain the result."
                )
        else:
            node = get_current_node(runtime_graph, assessment_state)
            deterministic = infer_answer_deterministically(node or {}, user_message, language, assessment_state)
            normalized = deterministic
            if deterministic.get("status") == "no_match" and isinstance(node, dict):
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

    elif mode == "post_assessment":
        if _looks_like_detailed_report(user_message):
            reply_text = _detailed_report_text(session.get("last_result"), language)
        elif _looks_like_explain_last_result(user_message):
            reply_text = explain_last_result(session.get("last_result"), language)
        elif _looks_like_result_request(user_message):
            reply_text = _result_text(session.get("last_result"), language)
        elif _looks_like_acknowledgement(user_message):
            session["mode"] = "free_conversation"
            reply_text = (
                "Хорошо. Если хотите, можете описать новый запрос, и я попробую подобрать другой assessment."
                if language == "ru"
                else "Okay. If you want, describe a new concern and I will try to find another assessment."
            )
        elif _is_greeting(user_message):
            session["mode"] = "free_conversation"
            reply_text = _greeting_text(language)
        else:
            candidates = await _find_graph_candidates(user_message, language)
            if candidates and float(candidates[0].get("score", 0.0)) >= 3.0:
                top = candidates[0]
                session["mode"] = "awaiting_consent"
                session["selected_graph_id"] = top.get("graph_id")
                session["discovered_graphs"] = [c.get("graph_id") for c in candidates if c.get("graph_id")]
                session["consent_status"] = "pending"
                reply_text = _offer_text(top, language)
            else:
                # Keep the session in post_assessment instead of dropping immediately to no-match.
                # This allows result-focused follow-ups to continue working.
                reply_text = (
                    "Я могу объяснить последний результат, дать краткий или подробный отчёт, либо помочь подобрать новый assessment по новому запросу."
                    if language == "ru"
                    else "I can explain the last result, give a short or detailed report, or help choose a new assessment for a new concern."
                )

    else:
        if _looks_like_explain_assessment(user_message):
            reply_text = (
                "Я могу помочь подобрать assessment из библиотеки graph-ов, предложить наиболее подходящий вариант и провести вас по нему шаг за шагом."
                if language == "ru"
                else "I can help select an assessment from the graph library, suggest the most relevant option, and guide you through it step by step."
            )
        elif _is_greeting(user_message):
            reply_text = _greeting_text(language)
        else:
            candidates = await _find_graph_candidates(user_message, language)
            if candidates and float(candidates[0].get("score", 0.0)) >= 3.0:
                top = candidates[0]
                session["mode"] = "awaiting_consent"
                session["selected_graph_id"] = top.get("graph_id")
                session["discovered_graphs"] = [c.get("graph_id") for c in candidates if c.get("graph_id")]
                session["consent_status"] = "pending"
                reply_text = _offer_text(top, language)
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
