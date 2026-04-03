from __future__ import annotations

from hea.shared.registry import get_graph, list_graphs
from hea.shared.patient_pipeline import analyze_patient_turn, extract_patient_intake
from hea.shared.runtime import (
    create_assessment_state,
    detailed_report,
    detect_language,
    explain_result,
    infer_turn_language,
    render_question,
)
from hea.shared.search import search_graphs


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _detect_language_switch(message: str) -> str | None:
    low = _normalize(message)
    if "русск" in low or "на русском" in low:
        return "ru"
    if "english" in low or "in english" in low:
        return "en"
    return None


def _is_greeting(message: str) -> bool:
    return _normalize(message) in {"/start", "привет", "здравствуйте", "hello", "hi"}


def _looks_like_ack(message: str) -> bool:
    return _normalize(message) in {"ок", "окей", "хорошо", "понял", "отлично", "ok", "okay", "great"}


def _looks_like_capabilities(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["что умеешь", "what can you do", "capabilities"])


def _looks_like_yes(message: str) -> bool:
    return _normalize(message) in {"да", "ок", "давай", "yes", "ok", "start"}


def _looks_like_no(message: str) -> bool:
    return _normalize(message) in {"нет", "no", "later", "not now"}


def _looks_like_pause(message: str) -> bool:
    return _normalize(message) in {"пауза", "pause"}


def _looks_like_cancel(message: str) -> bool:
    return _normalize(message) in {"стоп", "отмена", "cancel", "stop"}


def _looks_like_result(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["результат", "итог", "дай результат", "result", "summary"])


def _looks_like_explain(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["объясни", "обьясни", "что это значит", "explain"])


def _looks_like_report(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["подробный отчет", "подробный отчёт", "детальный отчет", "report", "detailed report"])


def _looks_like_pdf(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["pdf", "пдф", "скачай отчет", "скачай отчёт"])


def _looks_like_new_request(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["новый запрос", "по новому запросу", "давай новый запрос", "new request", "new concern", "something new"])


def _report_links_text(conversation_id: str | None, language: str) -> str:
    if not conversation_id:
        return ""
    if language == "ru":
        return (
            f"\n\nВеб-отчёт: `/report/{conversation_id}`"
            f"\nPDF-отчёт: `/report/{conversation_id}.pdf`"
        )
    return (
        f"\n\nWeb report: `/report/{conversation_id}`"
        f"\nPDF report: `/report/{conversation_id}.pdf`"
    )


def _humanize_candidate_reason(candidate: dict, language: str) -> str:
    metadata = candidate.get("metadata", {}) or {}
    topic = metadata.get("topic") or "assessment"
    artifact_type = metadata.get("artifact_type") or "questionnaire"
    raw_reason = str(candidate.get("reason") or "")
    if language == "ru":
        hints = []
        if "concept=" in raw_reason or "intake_topic=" in raw_reason or "topic" in raw_reason:
            hints.append(f"тема совпадает с запросом ({topic})")
        if "symptom=" in raw_reason or "signal=" in raw_reason:
            hints.append("есть совпадения по симптомам или сигналам входа")
        if "title" in raw_reason or "tag=" in raw_reason:
            hints.append("опросник размечен как релевантный")
        if artifact_type == "clinical_rule_graph":
            hints.append("это rule-based сценарий для раннего выявления")
        if not hints:
            hints.append("он лучше всего совпал с текущим запросом")
        return "Причина выбора: " + "; ".join(dict.fromkeys(hints)) + "."
    hints = []
    if "concept=" in raw_reason or "intake_topic=" in raw_reason or "topic" in raw_reason:
        hints.append(f"the topic matches your request ({topic})")
    if "symptom=" in raw_reason or "signal=" in raw_reason:
        hints.append("it matches the symptoms or entry signals")
    if "title" in raw_reason or "tag=" in raw_reason:
        hints.append("the assessment metadata is relevant")
    if artifact_type == "clinical_rule_graph":
        hints.append("it is a rule-based early-detection flow")
    if not hints:
        hints.append("it matched your request best")
    return "Why this assessment: " + "; ".join(dict.fromkeys(hints)) + "."


def greeting_text(language: str) -> str:
    if language == "ru":
        return (
            "Привет. Я могу пообщаться с вами в свободной форме, помочь понять запрос и при необходимости подобрать опросник или скрининговый сценарий из библиотеки.\n\n"
            "Можете просто рассказать, что вас беспокоит."
        )
    return (
        "Hi. I can talk with you freely, help understand your request, and select an assessment from the library when relevant.\n\n"
        "You can simply describe what is bothering you."
    )


def capabilities_text(language: str, in_assessment: bool = False) -> str:
    if in_assessment:
        return (
            "Сейчас мы внутри опроса. Я могу повторить вопрос, помочь с ответом, поставить опрос на паузу или остановить его."
            if language == "ru"
            else "We are currently inside an assessment. I can repeat the question, help with the answer, pause the assessment, or stop it."
        )

    graphs = list_graphs()
    if not graphs:
        return "В библиотеке пока нет доступных сценариев." if language == "ru" else "There are no graphs in the library yet."

    lines = [
        "Доступные опросники и сценарии:" if language == "ru" else "Available assessments:"
    ]
    for graph in graphs[:5]:
        lines.append(f"- {graph.get('title')} ({len(graph.get('questions', []))} questions)")
    return "\n".join(lines)


async def route_user_message(state: dict) -> dict:
    message = str(state.get("user_message") or "")
    language = infer_turn_language(message, str(state.get("language") or detect_language(message)))
    switch = _detect_language_switch(message)
    if switch:
        language = switch
    mode = str(state.get("mode") or "free_conversation")
    if mode == "post_assessment" and _looks_like_new_request(message):
        return {"language": language, "next_action": "RESET_TO_FREE"}
    if mode == "post_assessment":
        if _looks_like_explain(message):
            return {"language": language, "next_action": "EXPLAIN_LAST_RESULT"}
        if _looks_like_report(message) or _looks_like_pdf(message):
            return {"language": language, "next_action": "SHOW_LAST_REPORT"}
    if mode == "assessment_in_progress":
        if _looks_like_explain(message):
            return {"language": language, "next_action": "EXPLAIN_CURRENT_RESULT"}
        if _looks_like_report(message) or _looks_like_pdf(message):
            return {"language": language, "next_action": "SHOW_CURRENT_REPORT"}
    if _looks_like_cancel(message):
        return {"language": language, "next_action": "CANCEL"}
    intake = extract_patient_intake(message, state.get("symptom_intake"))
    decision = await analyze_patient_turn({**state, "language": language})
    return {
        "language": language,
        "next_action": decision.next_action,
        "analyst_decision": decision.model_dump(mode="json"),
        "red_flag_status": decision.red_flag_level,
        "symptom_summary": decision.symptom_summary,
        "symptom_intake": intake.model_dump(mode="json"),
    }


async def reset_and_greet(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {
        "mode": "free_conversation",
        "selected_graph_id": None,
        "selected_graph": None,
        "discovered_graphs": [],
        "consent_status": None,
        "assessment_state": None,
        "last_result": None,
        "assistant_reply": greeting_text(language),
    }


async def reset_to_free(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {
        "mode": "free_conversation",
        "selected_graph_id": None,
        "selected_graph": None,
        "discovered_graphs": [],
        "consent_status": None,
        "assessment_state": None,
        "last_result": None,
        "candidates": [],
        "red_flag_status": None,
        "symptom_summary": None,
        "last_search_query": None,
        "symptom_intake": None,
        "assistant_reply": (
            "Хорошо. Если хотите, можете описать новый запрос, и я попробую подобрать другой опросник."
            if language == "ru"
            else "Okay. If you want, describe a new concern and I will try to find another assessment."
        ),
    }


async def show_capabilities(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {"assistant_reply": capabilities_text(language, in_assessment=(state.get("mode") == "assessment_in_progress"))}


async def search_assessments(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    message = str(state.get("user_message") or "")
    summary = str(state.get("symptom_summary") or "").strip()
    intake = state.get("symptom_intake") or {}
    intake_context = " ".join(
        str(part)
        for part in [
            " ".join(intake.get("symptoms") or []),
            " ".join(intake.get("suspected_topics") or []),
            intake.get("duration") or "",
            intake.get("severity") or "",
            summary,
        ]
        if part
    )
    candidates = search_graphs(message, top_k=5, extra_context=intake_context, intake=intake)
    if candidates and float(candidates[0].get("score", 0.0)) >= 3.0:
        if len(candidates) > 1 and abs(float(candidates[0].get("score", 0.0)) - float(candidates[1].get("score", 0.0))) <= 2.0:
            lines = [
                "Я нашёл несколько похожих опросников. Выберите номер:" if language == "ru" else "I found several similar assessments. Choose a number:",
            ]
            if summary:
                lines.append(f"Контекст: {summary}" if language == "ru" else f"Context: {summary}")
            for idx, candidate in enumerate(candidates[:3], start=1):
                meta = candidate.get("metadata", {})
                lines.append(f"{idx}. {meta.get('title')} ({meta.get('questions_count')} questions)")
                reason = _humanize_candidate_reason(candidate, language)
                if reason:
                    lines.append(f"   {reason}")
            return {
                "mode": "awaiting_selection",
                "candidates": candidates,
                "last_search_query": message,
                "symptom_intake": intake,
                "assistant_reply": "\n".join(lines),
            }
        top = candidates[0]
        meta = top.get("metadata", {})
        rationale = _humanize_candidate_reason(top, language)
        return {
            "mode": "awaiting_consent",
            "selected_graph_id": top.get("graph_id"),
            "selected_graph": top.get("graph"),
            "discovered_graphs": [c.get("graph_id") for c in candidates if c.get("graph_id")],
            "consent_status": "pending",
            "candidates": candidates,
            "last_search_query": message,
            "symptom_intake": intake,
            "assistant_reply": (
                f"По вашему описанию вам может подойти опросник «{meta.get('title')}». "
                + (f"{rationale} " if rationale else "")
                + (f"Контекст: {summary}. " if summary else "")
                + (
                    f"Симптомы: {', '.join(intake.get('symptoms') or [])}. "
                    if intake.get("symptoms")
                    else ""
                )
                + f"Это примерно {meta.get('questions_count')} вопросов и около {meta.get('estimated_time_minutes')} минут. Хотите пройти его сейчас?"
                if language == "ru"
                else f"Based on what you described, a suitable assessment may be “{meta.get('title')}”. "
                     + (f"{rationale} " if rationale else "")
                     + (f"Context: {summary}. " if summary else "")
                     + (
                         f"Symptoms: {', '.join(intake.get('symptoms') or [])}. "
                         if intake.get("symptoms")
                         else ""
                     )
                     + f"It is about {meta.get('questions_count')} questions and around {meta.get('estimated_time_minutes')} minutes. Would you like to take it now?"
            ),
        }

    if state.get("mode") == "post_assessment":
        return {
            "assistant_reply": (
                "Я могу объяснить последний результат, дать подробный отчёт или помочь подобрать новый опросник по новому запросу."
                if language == "ru"
                else "I can explain the last result, provide a detailed report, or help choose a new assessment for a new concern."
            )
        }

    return {
        "assistant_reply": (
            "Я пока не нашёл явно подходящий опросник по этому описанию. Можете уточнить запрос."
            if language == "ru"
            else "I have not found a clearly suitable assessment for that description yet. You can clarify the request."
        )
    }


async def select_candidate(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    decision = state.get("analyst_decision") or {}
    try:
        index = int(decision.get("selected_candidate_index") or 0)
    except Exception:
        index = 0
    candidates = state.get("candidates") or []
    if index <= 0 or index > len(candidates):
        return {
            "assistant_reply": (
                "Не понял номер варианта. Выберите опросник по номеру из списка."
                if language == "ru"
                else "I could not understand the option number. Please choose an assessment by number."
            )
        }
    top = candidates[index - 1]
    meta = top.get("metadata", {})
    return {
        "mode": "awaiting_consent",
        "selected_graph_id": top.get("graph_id"),
        "selected_graph": top.get("graph"),
        "consent_status": "pending",
        "assistant_reply": (
            f"Вы выбрали опросник «{meta.get('title')}». Это примерно {meta.get('questions_count')} вопросов. Хотите пройти его сейчас?"
            if language == "ru"
            else f"You selected the assessment “{meta.get('title')}”. It is about {meta.get('questions_count')} questions. Would you like to start now?"
        ),
    }


async def restate_consent(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    graph = state.get("selected_graph") or {}
    title = graph.get("title") or "assessment"
    return {
        "assistant_reply": (
            f"Сейчас выбран опросник «{title}». Если хотите начать, ответьте `да`. Если не хотите, ответьте `нет`."
            if language == "ru"
            else f"The selected assessment is “{title}”. Reply `yes` to start or `no` to decline."
        )
    }


async def red_flag_guidance(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    level = str(state.get("red_flag_status") or "urgent")
    if language == "ru":
        if level == "emergency":
            return {
                "assistant_reply": (
                    "По вашему сообщению возможны тревожные симптомы. Я не буду продолжать обычный поиск опросника. "
                    "Если состояние острое или нарастает, лучше срочно обратиться за неотложной медицинской помощью."
                )
            }
        return {
            "assistant_reply": (
                "По вашему описанию есть признаки, которые лучше оценивать очно, а не только через screening-бот. "
                "Рекомендую связаться с врачом в ближайшее время. Если хотите, после этого я могу помочь подобрать неэкстренный опросник."
            )
        }
    if level == "emergency":
        return {
            "assistant_reply": (
                "Your message may describe warning symptoms. I will not continue with normal assessment search. "
                "If this is acute or getting worse, seek urgent medical care."
            )
        }
    return {
        "assistant_reply": (
            "Your description may include symptoms that are better evaluated in person rather than only through a screening bot. "
            "Please contact a clinician soon. After that, I can still help find a non-urgent assessment."
        )
    }


async def show_post_options(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {
        "assistant_reply": (
            "Я могу объяснить последний результат, показать подробный отчёт или помочь подобрать новый опросник по новому запросу."
            if language == "ru"
            else "I can explain the last result, show a detailed report, or help choose a new assessment for a new concern."
        )
    }


async def decline_assessment(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {
        "mode": "free_conversation",
        "consent_status": "declined",
        "selected_graph_id": None,
        "selected_graph": None,
        "assistant_reply": (
            "Хорошо, не будем запускать опрос сейчас."
            if language == "ru"
            else "Okay, we do not have to start the assessment right now."
        ),
    }


async def start_assessment(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    graph = state.get("selected_graph")
    if not graph and state.get("selected_graph_id"):
        graph = get_graph(str(state["selected_graph_id"]))
    if not graph:
        return {"assistant_reply": "Graph not found."}
    assessment_state = create_assessment_state(graph, language)
    return {
        "mode": "assessment_in_progress",
        "assessment_state": assessment_state,
        "selected_graph": graph,
        "assistant_reply": render_question(graph, assessment_state),
    }


async def pause_assessment(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {
        "mode": "paused_assessment",
        "assistant_reply": (
            "Хорошо, поставим опрос на паузу. Когда захотите продолжить, просто напишите."
            if language == "ru"
            else "Okay, we can pause the assessment here. When you want to continue, just send a message."
        ),
    }


async def resume_assessment(state: dict) -> dict:
    graph = state.get("selected_graph") or {}
    assessment_state = state.get("assessment_state") or {}
    return {
        "mode": "assessment_in_progress",
        "assistant_reply": render_question(graph, assessment_state),
    }


async def cancel_assessment(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {
        "mode": "free_conversation",
        "selected_graph_id": None,
        "selected_graph": None,
        "consent_status": None,
        "assessment_state": None,
        "assistant_reply": (
            "Хорошо, я остановил текущий опрос."
            if language == "ru"
            else "Okay, I stopped the current assessment."
        ),
    }


async def show_paused(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {
        "assistant_reply": (
            "Сейчас опрос на паузе. Напишите 'продолжить', чтобы вернуться."
            if language == "ru"
            else "The assessment is currently paused. Send 'continue' to resume."
        )
    }


async def show_current_result(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {"assistant_reply": _result_text(state.get("assessment_state", {}).get("result"), language)}


def _result_text(result: dict | None, language: str) -> str:
    if not isinstance(result, dict):
        return "Результат пока недоступен." if language == "ru" else "The result is not available yet."
    risk_band = result.get("risk_band") or {}
    return (
        f"Тема: {result.get('graph_title')}\nСуммарный балл: {result.get('score_total')}\nКатегория: {risk_band.get('label', '—')}"
        if language == "ru"
        else f"Topic: {result.get('graph_title')}\nTotal score: {result.get('score_total')}\nCategory: {risk_band.get('label', '—')}"
    )


async def show_current_report(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    reply = detailed_report(state.get("assessment_state", {}).get("result"), language)
    reply += _report_links_text(state.get("conversation_id"), language)
    return {"assistant_reply": reply}


async def explain_current_result(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {"assistant_reply": explain_result(state.get("assessment_state", {}).get("result"), language)}


async def show_last_result(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {"assistant_reply": _result_text(state.get("last_result"), language)}


async def show_last_report(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    reply = detailed_report(state.get("last_result"), language)
    reply += _report_links_text(state.get("conversation_id"), language)
    return {"assistant_reply": reply}


async def explain_last_result_node(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {"assistant_reply": explain_result(state.get("last_result"), language)}
