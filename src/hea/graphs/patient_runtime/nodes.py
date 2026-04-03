from __future__ import annotations

from hea.shared.runtime import (
    apply_answer,
    explain_result,
    normalize_answer,
    render_question,
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def route_runtime_message(state: dict) -> dict:
    message = str(state.get("user_message") or "")
    low = _normalize(message)

    if "повтори" in low or "repeat" in low:
        return {"next_action": "REPEAT"}
    if "помоги" in low or "help" in low:
        return {"next_action": "HELP"}
    if "объясни" in low or "обьясни" in low or "explain" in low:
        return {"next_action": "EXPLAIN_RESULT"}
    return {"next_action": "ANSWER"}


def repeat_question_node(state: dict) -> dict:
    return {"assistant_reply": render_question(state["graph"], state["assessment_state"])}


def help_node(state: dict) -> dict:
    language = state["assessment_state"].get("language", "ru")
    help_text = (
        "Ответьте номером варианта или текстом варианта."
        if language == "ru"
        else "Reply with the option number or the option text."
    )
    return {"assistant_reply": help_text + "\n\n" + render_question(state["graph"], state["assessment_state"])}


def explain_result_node(state: dict) -> dict:
    language = state["assessment_state"].get("language", "ru")
    return {"assistant_reply": explain_result(state["assessment_state"].get("result"), language)}


def answer_node(state: dict) -> dict:
    graph = state["graph"]
    assessment_state = state["assessment_state"]
    normalized = normalize_answer(
        graph["questions"][assessment_state["question_index"]],
        str(state.get("user_message") or ""),
    )
    result = apply_answer(graph, assessment_state, normalized)
    return {
        "assessment_state": result["assessment_state"],
        "assistant_reply": result["reply_text"],
    }
