from __future__ import annotations

import re
from typing import Any


YES_WORDS_RU = {"да", "ага", "угу", "есть", "было", "конечно", "хочу", "начнем", "начинаем"}
NO_WORDS_RU = {"нет", "не", "не было", "отсутствует", "не хочу"}
YES_WORDS_EN = {"yes", "y", "yeah", "yep", "true", "sure", "start"}
NO_WORDS_EN = {"no", "n", "nope", "false"}

MALE_WORDS = {"мужчина", "мужской", "male", "man", "парень", "м"}
FEMALE_WORDS = {"женщина", "женский", "female", "woman", "девушка", "ж"}


def detect_language(text: str) -> str:
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "ru"
    return "en"


def localize_text(value: Any, language: str, fallback: str = "") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        chosen = value.get(language)
        if isinstance(chosen, str) and chosen.strip():
            return chosen
        for candidate in value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    return fallback


def extract_runtime_graph(graph_record: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(graph_record, dict):
        return {
            "graph_id": None,
            "title": "assessment",
            "topic": "assessment",
            "entry_node_id": None,
            "nodes": [],
            "risk_bands": [],
            "scoring": {},
        }

    graph_id = graph_record.get("graph_id")
    graph = graph_record.get("graph", {})
    if not isinstance(graph, dict):
        graph = {}

    if isinstance(graph.get("nodes"), list) and graph.get("nodes"):
        return {
            "graph_id": graph_id,
            "title": graph.get("title") or graph.get("topic") or graph_id or "assessment",
            "topic": graph.get("topic") or graph.get("title") or "assessment",
            "entry_node_id": graph.get("entry_node_id") or _first_node_id(graph.get("nodes")),
            "nodes": _normalize_nodes(graph.get("nodes")),
            "risk_bands": graph.get("risk_bands", []) if isinstance(graph.get("risk_bands"), list) else [],
            "scoring": graph.get("scoring", {}) if isinstance(graph.get("scoring"), dict) else {},
        }

    questions = graph.get("questions")
    if not isinstance(questions, list):
        source_draft = graph.get("source_draft", {})
        if isinstance(source_draft, dict):
            questions = source_draft.get("candidate_questions", [])
        else:
            questions = []

    source_draft = graph.get("source_draft", {})
    if not isinstance(source_draft, dict):
        source_draft = {}

    return build_sequential_runtime_graph(
        graph_id=graph_id,
        title=graph.get("title") or graph.get("topic") or graph_id or "assessment",
        topic=graph.get("topic") or graph.get("title") or "assessment",
        questions=questions if isinstance(questions, list) else [],
        risk_bands=graph.get("risk_bands", []) if isinstance(graph.get("risk_bands"), list) else (
            source_draft.get("candidate_risk_bands", []) if isinstance(source_draft.get("candidate_risk_bands"), list) else []
        ),
        scoring=graph.get("scoring", {}) if isinstance(graph.get("scoring"), dict) else (
            source_draft.get("candidate_scoring_rules", {}) if isinstance(source_draft.get("candidate_scoring_rules"), dict) else {}
        ),
    )


def build_sequential_runtime_graph(
    *,
    graph_id: str | None,
    title: str,
    topic: str,
    questions: list[dict[str, Any]],
    risk_bands: list[dict[str, Any]],
    scoring: dict[str, Any],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []

    for idx, raw_q in enumerate(questions):
        if not isinstance(raw_q, dict):
            continue

        node_id = str(raw_q.get("id") or f"q{idx + 1}")
        next_id = str(questions[idx + 1].get("id") or f"q{idx + 2}") if idx + 1 < len(questions) and isinstance(questions[idx + 1], dict) else "result"
        q_type, normalization_rule, validation_rule = infer_runtime_rules(raw_q)

        nodes.append(
            {
                "id": node_id,
                "type": "question",
                "question_type": raw_q.get("question_type", q_type),
                "text": raw_q.get("text", f"Question {idx + 1}"),
                "help_text": raw_q.get("help_text") or _default_help_for_question(raw_q, q_type),
                "why_it_matters": raw_q.get("why_it_matters"),
                "options": _normalize_options(raw_q.get("options")),
                "normalization_rule": raw_q.get("normalization_rule") or normalization_rule,
                "validation_rule": raw_q.get("validation_rule") or validation_rule,
                "scoring_rule": raw_q.get("scoring_rule") or {"type": "selected_option_score"},
                "next": {"default": next_id},
            }
        )

    nodes.append(
        {
            "id": "result",
            "type": "result",
            "text": {"ru": "Результат assessment", "en": "Assessment result"},
            "next": {},
        }
    )

    return {
        "graph_id": graph_id,
        "title": title,
        "topic": topic,
        "entry_node_id": nodes[0]["id"] if nodes else None,
        "nodes": nodes,
        "risk_bands": risk_bands if isinstance(risk_bands, list) else [],
        "scoring": scoring if isinstance(scoring, dict) else {},
    }


def infer_runtime_rules(question: dict[str, Any]) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    text = str(question.get("text", "")).lower()
    options = question.get("options", [])
    options = options if isinstance(options, list) else []

    if options:
        labels = [str((o.get("label") if isinstance(o, dict) else o) or "").lower() for o in options]
        if all(lbl in {"да", "нет", "yes", "no", "true", "false"} for lbl in labels if lbl):
            return "boolean", None, None
        if any(_parse_range_label(str((o.get("label") if isinstance(o, dict) else o) or "")) for o in options):
            return "numeric_or_option", {"type": "match_numeric_to_option_label"}, None
        return "single_choice", None, None

    if "возраст" in text or "age" in text:
        return "numeric_or_text", None, {"min_value": 0, "max_value": 120}
    if "индекс массы тела" in text or "имт" in text or "bmi" in text:
        return "numeric_or_text", None, {"min_value": 10, "max_value": 100}
    if "талии" in text or "waist" in text:
        return "numeric_or_text", None, {"min_value": 20, "max_value": 300}

    return "free_text", None, None


def graph_meta(runtime_graph: dict[str, Any], language: str) -> dict[str, Any]:
    title = localize_text(runtime_graph.get("title"), language) or runtime_graph.get("topic") or "assessment"
    topic = runtime_graph.get("topic") or title
    questions_count = len([n for n in runtime_graph.get("nodes", []) if isinstance(n, dict) and n.get("type") == "question"])
    return {"title": title, "topic": topic, "questions_count": questions_count}


def create_assessment_state(runtime_graph: dict[str, Any], language: str) -> dict[str, Any]:
    return {
        "status": "idle",
        "language": language,
        "current_node_id": runtime_graph.get("entry_node_id"),
        "answers": [],
        "score_total": 0.0,
        "result": None,
        "pending_slots": {},
    }


def get_node_map(runtime_graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    node_map: dict[str, dict[str, Any]] = {}
    for node in runtime_graph.get("nodes", []):
        if isinstance(node, dict) and node.get("id"):
            node_map[str(node["id"])] = node
    return node_map


def get_current_node(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> dict[str, Any] | None:
    node_map = get_node_map(runtime_graph)
    node_id = assessment_state.get("current_node_id")
    if not isinstance(node_id, str):
        return None
    return node_map.get(node_id)


def start_assessment(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> dict[str, Any]:
    assessment_state["status"] = "in_progress"
    node = get_current_node(runtime_graph, assessment_state)
    if not node:
        return {
            "reply_text": _localized_text(
                {"ru": "Сейчас нет доступного вопроса.", "en": "There is no available question right now."},
                assessment_state["language"],
            ),
            "assessment_state": assessment_state,
        }
    return render_node_prompt(runtime_graph, assessment_state, node)


def render_node_prompt(runtime_graph: dict[str, Any], assessment_state: dict[str, Any], node: dict[str, Any], prefix_text: str | None = None) -> dict[str, Any]:
    language = assessment_state["language"]

    if node.get("type") == "question":
        questions = [n for n in runtime_graph.get("nodes", []) if isinstance(n, dict) and n.get("type") == "question"]
        question_ids = [str(q.get("id")) for q in questions]
        current_id = str(node.get("id"))
        idx = question_ids.index(current_id) if current_id in question_ids else 0

        text = _localized_text(node.get("text"), language, fallback="Question")
        parts: list[str] = []
        if prefix_text:
            parts.append(prefix_text)
            parts.append("")
        parts.append(f"{'Вопрос' if language == 'ru' else 'Question'} {idx + 1}/{len(questions)}: {text}")

        options = node.get("options", [])
        if isinstance(options, list) and options:
            parts.append("")
            parts.append("Варианты ответа:" if language == "ru" else "Answer options:")
            for i, option in enumerate(options, start=1):
                if isinstance(option, dict):
                    parts.append(f"{i}. {option.get('label', '—')}")
            parts.append("")
            parts.append(
                "Можно ответить номером, текстом варианта или своими словами — я постараюсь понять смысл."
                if language == "ru"
                else "You can answer with the option number, the option text, or in your own words — I will try to understand the meaning."
            )
        else:
            parts.append("")
            parts.append(
                "Можете ответить в свободной форме. Если уместно, можно просто написать число."
                if language == "ru"
                else "You can answer in free form. When appropriate, you can just send a number."
            )

        return {"reply_text": "\n".join(parts), "assessment_state": assessment_state}

    if node.get("type") in {"result", "terminal"}:
        return build_result(runtime_graph, assessment_state)

    return {"reply_text": _localized_text(node.get("text"), language, fallback=""), "assessment_state": assessment_state}


def explain_current_question(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> str:
    node = get_current_node(runtime_graph, assessment_state)
    if not node:
        return _localized_text(
            {"ru": "Сейчас у меня нет активного вопроса.", "en": "I do not have an active question right now."},
            assessment_state["language"],
        )

    why = _localized_text(node.get("why_it_matters"), assessment_state["language"])
    if why:
        return why

    return _localized_text(
        {"ru": "Этот вопрос помогает точнее определить итог assessment.", "en": "This question helps make the assessment result more accurate."},
        assessment_state["language"],
    )


def help_with_current_question(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> str:
    node = get_current_node(runtime_graph, assessment_state)
    if not node:
        return _localized_text(
            {"ru": "Сейчас у меня нет активного вопроса.", "en": "I do not have an active question right now."},
            assessment_state["language"],
        )

    help_text = _localized_text(node.get("help_text"), assessment_state["language"])
    if help_text:
        return help_text

    return _localized_text(
        {"ru": "Вы можете ответить своими словами, а я постараюсь привести ответ к нужному формату.", "en": "You can answer in your own words, and I will try to normalize it into the expected format."},
        assessment_state["language"],
    )


def repeat_current_question(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> str:
    node = get_current_node(runtime_graph, assessment_state)
    if not node:
        return _localized_text(
            {"ru": "Сейчас у меня нет активного вопроса.", "en": "I do not have an active question right now."},
            assessment_state["language"],
        )
    rendered = render_node_prompt(runtime_graph, assessment_state, node)
    return rendered["reply_text"]


def normalize_yes_no(message: str) -> bool | None:
    low = _normalize(message)
    if low in YES_WORDS_RU or low in YES_WORDS_EN:
        return True
    if low in NO_WORDS_RU or low in NO_WORDS_EN:
        return False
    return None


def infer_answer_deterministically(node: dict[str, Any], user_message: str, language: str, assessment_state: dict[str, Any] | None = None) -> dict[str, Any]:
    assessment_state = assessment_state or {}
    text = user_message.strip()
    low = _normalize(text)
    options = node.get("options", [])
    options = options if isinstance(options, list) else []
    question_type = node.get("question_type", "single_choice")
    pending_slots = assessment_state.get("pending_slots", {}) if isinstance(assessment_state.get("pending_slots"), dict) else {}

    yes_no = normalize_yes_no(text)
    if yes_no is not None:
        if options:
            match = _match_yes_no_to_option(options, yes_no)
            if match:
                return {
                    "status": "full_match",
                    "raw_answer": user_message,
                    "value": match.get("value", yes_no),
                    "selected_option": match.get("label"),
                    "score": float(match.get("score", 0.0)),
                }
        if question_type == "boolean":
            return {
                "status": "full_match",
                "raw_answer": user_message,
                "value": yes_no,
                "selected_option": None,
                "score": 0.0,
            }

    if options:
        by_index = _match_option_by_index(options, low)
        if by_index:
            return {
                "status": "full_match",
                "raw_answer": user_message,
                "value": by_index.get("value"),
                "selected_option": by_index.get("label"),
                "score": float(by_index.get("score", 0.0)),
            }
        by_label = _match_option_by_label(options, low)
        if by_label:
            return {
                "status": "full_match",
                "raw_answer": user_message,
                "value": by_label.get("value"),
                "selected_option": by_label.get("label"),
                "score": float(by_label.get("score", 0.0)),
            }

    partial_slots = _extract_partial_slots(node, text, language)
    if partial_slots:
        current_slots = dict(pending_slots)
        current_slots.update(partial_slots)
        missing = _missing_slots_for_node(node, current_slots)
        return {
            "status": "partial_match",
            "raw_answer": user_message,
            "slots": current_slots,
            "missing_slots": missing,
        }

    numeric = _extract_float(text)
    if numeric is not None:
        semantic_mismatch = _detect_semantic_mismatch(node, text)
        if semantic_mismatch:
            return {
                "status": "semantic_mismatch",
                "raw_answer": user_message,
                "reason": semantic_mismatch,
            }

        validation_rule = node.get("validation_rule")
        if isinstance(validation_rule, dict):
            min_value = validation_rule.get("min_value")
            max_value = validation_rule.get("max_value")
            if min_value is not None and numeric < float(min_value):
                return {"status": "semantic_mismatch", "raw_answer": user_message, "reason": "value_too_small"}
            if max_value is not None and numeric > float(max_value):
                return {"status": "semantic_mismatch", "raw_answer": user_message, "reason": "value_too_large"}

        normalization_rule = node.get("normalization_rule")
        if isinstance(normalization_rule, dict) and normalization_rule.get("type") == "match_numeric_to_option_label" and options:
            sex_context = pending_slots.get("sex")
            if sex_context is None and _labels_require_sex(options):
                return {
                    "status": "partial_match",
                    "raw_answer": user_message,
                    "slots": dict(pending_slots),
                    "missing_slots": ["sex"],
                    "numeric_value": numeric,
                }

            matched = _match_numeric_to_option_label(options, numeric, sex_context)
            if matched:
                return {
                    "status": "full_match",
                    "raw_answer": user_message,
                    "value": matched.get("value"),
                    "selected_option": matched.get("label"),
                    "score": float(matched.get("score", 0.0)),
                }

        if question_type in {"numeric_or_text", "numeric_or_option", "numeric", "number"}:
            return {
                "status": "full_match",
                "raw_answer": user_message,
                "value": numeric,
                "selected_option": None,
                "score": 0.0,
            }

    if question_type in {"free_text", "text", "numeric_or_text"}:
        return {
            "status": "full_match",
            "raw_answer": user_message,
            "value": text,
            "selected_option": None,
            "score": 0.0,
        }

    return {"status": "no_match", "raw_answer": user_message}


def answer_current_question(runtime_graph: dict[str, Any], assessment_state: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    node = get_current_node(runtime_graph, assessment_state)
    language = assessment_state["language"]

    if not node:
        return {
            "reply_text": _localized_text(
                {"ru": "Сейчас нет активного вопроса.", "en": "There is no active question right now."},
                language,
            ),
            "assessment_state": assessment_state,
            "completed": False,
        }

    status = normalized.get("status")

    if status == "partial_match":
        slots = normalized.get("slots", {})
        if isinstance(slots, dict):
            assessment_state["pending_slots"] = slots

        followup = _build_partial_followup(node, normalized, language)
        prompt = repeat_current_question(runtime_graph, assessment_state)
        return {
            "reply_text": followup + "\n\n" + prompt,
            "assessment_state": assessment_state,
            "completed": False,
        }

    if status == "semantic_mismatch":
        followup = _build_semantic_mismatch_followup(node, normalized, language)
        prompt = repeat_current_question(runtime_graph, assessment_state)
        return {
            "reply_text": followup + "\n\n" + prompt,
            "assessment_state": assessment_state,
            "completed": False,
        }

    if status != "full_match":
        prompt = repeat_current_question(runtime_graph, assessment_state)
        reply = (
            "Я не смог понять ответ. Давайте попробуем ещё раз.\n\n" + prompt
            if language == "ru"
            else "I could not understand that answer. Let's try again.\n\n" + prompt
        )
        return {"reply_text": reply, "assessment_state": assessment_state, "completed": False}

    answer_record = {
        "node_id": node.get("id"),
        "question_text": _localized_text(node.get("text"), language, fallback=str(node.get("id"))),
        "raw_answer": normalized.get("raw_answer"),
        "normalized_value": normalized.get("value"),
        "selected_option": normalized.get("selected_option"),
        "score": float(normalized.get("score", 0.0)),
        "used_slots": assessment_state.get("pending_slots", {}),
    }
    assessment_state["answers"].append(answer_record)
    assessment_state["score_total"] = float(assessment_state.get("score_total", 0.0)) + float(normalized.get("score", 0.0))
    assessment_state["pending_slots"] = {}

    next_node_id = resolve_next_node_id(node, normalized)
    if not next_node_id:
        result = build_result(runtime_graph, assessment_state)
        return {"reply_text": result["reply_text"], "assessment_state": result["assessment_state"], "completed": True}

    assessment_state["current_node_id"] = next_node_id
    next_node = get_current_node(runtime_graph, assessment_state)
    if not next_node or next_node.get("type") in {"result", "terminal"}:
        result = build_result(runtime_graph, assessment_state)
        return {"reply_text": result["reply_text"], "assessment_state": result["assessment_state"], "completed": True}

    rendered = render_node_prompt(runtime_graph, assessment_state, next_node)
    return {"reply_text": rendered["reply_text"], "assessment_state": rendered["assessment_state"], "completed": False}


def resolve_next_node_id(node: dict[str, Any], normalized: dict[str, Any]) -> str | None:
    next_map = node.get("next", {})
    if not isinstance(next_map, dict):
        return None

    selected = normalized.get("selected_option")
    normalized_value = str(normalized.get("value")).lower() if normalized.get("value") is not None else None

    if isinstance(selected, str):
        if selected in next_map:
            return next_map[selected]
        low_selected = selected.lower()
        if low_selected in next_map:
            return next_map[low_selected]

    if normalized_value and normalized_value in next_map:
        return next_map[normalized_value]

    return next_map.get("default")


def build_result(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> dict[str, Any]:
    language = assessment_state["language"]
    score_total = float(assessment_state.get("score_total", 0.0))
    risk_band = find_risk_band(score_total, runtime_graph.get("risk_bands", []))
    meta = graph_meta(runtime_graph, language)

    assessment_state["status"] = "completed"
    assessment_state["result"] = {
        "score_total": score_total,
        "risk_band": risk_band,
        "graph_title": meta["title"],
        "topic": meta["topic"],
    }

    if language == "ru":
        if risk_band:
            label = risk_band.get("label", "неизвестно")
            reply_text = (
                f"Спасибо, assessment завершён.\n\n"
                f"Тема: {meta['title']}\n"
                f"Суммарный балл: {score_total:g}\n"
                f"Категория результата: {label}\n\n"
                f"Если хотите, я могу кратко объяснить результат или помочь подобрать другой assessment."
            )
        else:
            reply_text = (
                f"Спасибо, assessment завершён.\n\n"
                f"Тема: {meta['title']}\n"
                f"Суммарный балл: {score_total:g}\n\n"
                f"Если хотите, я могу кратко объяснить результат или помочь подобрать другой assessment."
            )
    else:
        if risk_band:
            label = risk_band.get("label", "unknown")
            reply_text = (
                f"Thank you, the assessment is complete.\n\n"
                f"Topic: {meta['title']}\n"
                f"Total score: {score_total:g}\n"
                f"Result category: {label}\n\n"
                f"If you want, I can briefly explain the result or help choose another assessment."
            )
        else:
            reply_text = (
                f"Thank you, the assessment is complete.\n\n"
                f"Topic: {meta['title']}\n"
                f"Total score: {score_total:g}\n\n"
                f"If you want, I can briefly explain the result or help choose another assessment."
            )

    return {"reply_text": reply_text, "assessment_state": assessment_state}


def explain_last_result(last_result: dict[str, Any] | None, language: str) -> str:
    if not isinstance(last_result, dict):
        return (
            "Сейчас у меня нет завершённого результата для объяснения."
            if language == "ru"
            else "I do not have a completed result to explain right now."
        )

    score_total = last_result.get("score_total")
    graph_title = last_result.get("graph_title")
    risk_band = last_result.get("risk_band") or {}
    label = risk_band.get("label")
    meaning = risk_band.get("meaning")

    if language == "ru":
        if label and meaning:
            return (
                f"По assessment «{graph_title}» у вас итоговый балл {score_total} и категория «{label}».\n"
                f"В логике этого graph это означает: {meaning}.\n\n"
                f"Это результат screening assessment, а не диагноз."
            )
        if label:
            return (
                f"По assessment «{graph_title}» у вас итоговый балл {score_total} и категория «{label}».\n\n"
                f"Это результат screening assessment, а не диагноз."
            )
        return (
            f"По assessment «{graph_title}» у вас итоговый балл {score_total}.\n\n"
            f"Это результат screening assessment, а не диагноз."
        )

    if label and meaning:
        return (
            f"For the assessment “{graph_title}”, your total score is {score_total} and the category is “{label}”.\n"
            f"In this graph, that means: {meaning}.\n\n"
            f"This is a screening assessment result, not a diagnosis."
        )
    if label:
        return (
            f"For the assessment “{graph_title}”, your total score is {score_total} and the category is “{label}”.\n\n"
            f"This is a screening assessment result, not a diagnosis."
        )
    return (
        f"For the assessment “{graph_title}”, your total score is {score_total}.\n\n"
        f"This is a screening assessment result, not a diagnosis."
    )


def find_risk_band(score_total: float, risk_bands: list[dict[str, Any]]) -> dict[str, Any] | None:
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


def _extract_partial_slots(node: dict[str, Any], user_message: str, language: str) -> dict[str, Any]:
    text = _normalize(user_message)
    question_text = _normalize(str(node.get("text", "")))

    slots: dict[str, Any] = {}
    if "талии" in question_text or "waist" in question_text:
        if any(word in text for word in MALE_WORDS):
            slots["sex"] = "male"
        elif any(word in text for word in FEMALE_WORDS):
            slots["sex"] = "female"

    return slots


def _missing_slots_for_node(node: dict[str, Any], current_slots: dict[str, Any]) -> list[str]:
    question_text = _normalize(str(node.get("text", "")))
    missing: list[str] = []

    if "талии" in question_text or "waist" in question_text:
        if "sex" not in current_slots:
            missing.append("sex")
        if "waist_cm" not in current_slots:
            missing.append("waist_cm")

    return missing


def _build_partial_followup(node: dict[str, Any], normalized: dict[str, Any], language: str) -> str:
    slots = normalized.get("slots", {})
    missing = normalized.get("missing_slots", [])
    question_text = _normalize(str(node.get("text", "")))

    if ("талии" in question_text or "waist" in question_text) and isinstance(slots, dict):
        sex = slots.get("sex")
        if sex == "male" and "waist_cm" in missing:
            return (
                "Понял, вы мужчина. Теперь напишите окружность талии в сантиметрах."
                if language == "ru"
                else "Got it, you are male. Now please send your waist circumference in centimeters."
            )
        if sex == "female" and "waist_cm" in missing:
            return (
                "Понял, вы женщина. Теперь напишите окружность талии в сантиметрах."
                if language == "ru"
                else "Got it, you are female. Now please send your waist circumference in centimeters."
            )

    return (
        "Я понял ответ только частично. Давайте уточним недостающую часть."
        if language == "ru"
        else "I only understood part of the answer. Let’s clarify the missing part."
    )


def _build_semantic_mismatch_followup(node: dict[str, Any], normalized: dict[str, Any], language: str) -> str:
    reason = normalized.get("reason")
    question_text = _normalize(str(node.get("text", "")))

    if reason == "bmi_unit_mismatch":
        return (
            "Похоже, вы указали вес в килограммах, а здесь нужен ИМТ. Если знаете ИМТ, напишите его числом, например 27.5."
            if language == "ru"
            else "It looks like you gave weight in kilograms, but this question expects BMI. If you know your BMI, send it as a number, for example 27.5."
        )

    if reason == "value_too_small" or reason == "value_too_large":
        return (
            "Похоже, значение не подходит для этого вопроса. Попробуйте ответить ещё раз в ожидаемом формате."
            if language == "ru"
            else "That value does not seem to fit this question. Please try again in the expected format."
        )

    if "талии" in question_text or "waist" in question_text:
        return (
            "Для этого вопроса нужен понятный ответ по окружности талии. Если хотите, сначала можно указать пол, а потом число в сантиметрах."
            if language == "ru"
            else "This question needs a clear waist measurement answer. If you want, you can first specify sex, then send the number in centimeters."
        )

    return (
        "Похоже, ответ не подходит по формату или смыслу для этого вопроса. Давайте уточним."
        if language == "ru"
        else "That answer does not seem to match the expected format or meaning for this question. Let’s clarify it."
    )


def _detect_semantic_mismatch(node: dict[str, Any], raw_text: str) -> str | None:
    text = _normalize(raw_text)
    question_text = _normalize(str(node.get("text", "")))

    if "имт" in question_text or "bmi" in question_text or "индекс массы тела" in question_text:
        if "килограмм" in text or "kg" in text or "кг" in text:
            if "/" not in text and "м2" not in text and "м²" not in text:
                return "bmi_unit_mismatch"

    return None


def _labels_require_sex(options: list[dict[str, Any]]) -> bool:
    for option in options:
        label = _normalize(str(option.get("label", "")))
        if "мужчина" in label or "женщина" in label or "male" in label or "female" in label:
            return True
    return False


def _match_yes_no_to_option(options: list[dict[str, Any]], yes_no: bool) -> dict[str, Any] | None:
    target_words = {"да", "yes", "true"} if yes_no else {"нет", "no", "false"}
    for option in options:
        label = _normalize(str(option.get("label", "")))
        if label in target_words:
            return option
    return None


def _match_option_by_index(options: list[dict[str, Any]], low: str) -> dict[str, Any] | None:
    if not low.isdigit():
        return None
    idx = int(low) - 1
    if 0 <= idx < len(options):
        return options[idx]
    return None


def _match_option_by_label(options: list[dict[str, Any]], low: str) -> dict[str, Any] | None:
    for option in options:
        label = _normalize(str(option.get("label", "")))
        if label == low:
            return option
    for option in options:
        label = _normalize(str(option.get("label", "")))
        if low and low in label:
            return option
    return None


def _extract_float(text: str) -> float | None:
    match = re.search(r"(-?\d+(?:[.,]\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except Exception:
        return None


def _match_numeric_to_option_label(options: list[dict[str, Any]], value: float, sex_context: str | None = None) -> dict[str, Any] | None:
    for option in options:
        label = str(option.get("label", "")).strip()
        low_label = _normalize(label)

        if sex_context == "male" and ("женщина" in low_label or "female" in low_label):
            continue
        if sex_context == "female" and ("мужчина" in low_label or "male" in low_label):
            continue

        parsed = _parse_range_label(label)
        if not parsed:
            continue

        kind = parsed["kind"]
        if kind == "lt" and value < parsed["max"]:
            return option
        if kind == "gt" and value > parsed["min"]:
            return option
        if kind == "ge" and value >= parsed["min"]:
            return option
        if kind == "range" and parsed["min"] <= value <= parsed["max"]:
            return option
    return None


def _normalize_options(options: Any) -> list[dict[str, Any]]:
    if not isinstance(options, list):
        return []

    normalized: list[dict[str, Any]] = []
    for idx, option in enumerate(options):
        if isinstance(option, str):
            normalized.append({"id": f"opt_{idx + 1}", "label": option, "value": option, "score": 0.0})
            continue
        if not isinstance(option, dict):
            continue
        label = option.get("label") or option.get("text") or option.get("value") or f"Option {idx + 1}"
        normalized.append(
            {
                "id": str(option.get("id") or f"opt_{idx + 1}"),
                "label": label,
                "value": option.get("value", label),
                "score": float(option.get("score", 0.0)) if option.get("score") is not None else 0.0,
                "notes": option.get("notes"),
            }
        )
    return normalized


def _default_help_for_question(question: dict[str, Any], q_type: str) -> dict[str, str] | str | None:
    if q_type in {"numeric_or_text", "numeric_or_option"}:
        return {
            "ru": "Можно ответить числом, например 30 или 27.5. Я постараюсь сам привести ответ к нужному формату.",
            "en": "You can answer with a number, for example 30 or 27.5. I will try to normalize it to the expected format.",
        }
    options = question.get("options")
    if isinstance(options, list) and options:
        return {
            "ru": "Можно ответить номером варианта, текстом варианта или своими словами, если смысл совпадает.",
            "en": "You can answer with the option number, the option text, or in your own words if the meaning matches.",
        }
    return {
        "ru": "Ответьте так, как вам удобнее. Если нужно, я помогу уточнить формат.",
        "en": "Answer in the way that feels easiest. If needed, I can help clarify the format.",
    }


def _first_node_id(nodes: list[Any]) -> str | None:
    for node in nodes:
        if isinstance(node, dict) and node.get("id"):
            return str(node["id"])
    return None


def _normalize_nodes(nodes: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for idx, raw in enumerate(nodes):
        if not isinstance(raw, dict):
            continue
        q_type, normalization_rule, validation_rule = infer_runtime_rules(raw)
        normalized.append(
            {
                "id": str(raw.get("id") or f"node_{idx + 1}"),
                "type": raw.get("type", "question"),
                "question_type": raw.get("question_type", q_type),
                "text": raw.get("text", f"Node {idx + 1}"),
                "help_text": raw.get("help_text"),
                "why_it_matters": raw.get("why_it_matters"),
                "options": _normalize_options(raw.get("options")),
                "normalization_rule": raw.get("normalization_rule") or normalization_rule,
                "validation_rule": raw.get("validation_rule") or validation_rule,
                "scoring_rule": raw.get("scoring_rule") or {"type": "selected_option_score"},
                "next": raw.get("next", {}) if isinstance(raw.get("next"), dict) else {},
            }
        )
    return normalized


def _parse_range_label(label: str) -> dict[str, Any] | None:
    normalized = label.lower()
    normalized = normalized.replace("–", "-").replace("—", "-").replace("−", "-")
    normalized = re.sub(r"(мужчина:|женщина:|male:|female:)", "", normalized).strip()
    normalized = normalized.replace("см", "").replace("kg/m²", "").replace("kg/m2", "").replace("кг/м²", "").replace("кг/м2", "")
    normalized = re.sub(r"\s+", "", normalized)

    m = re.match(r"^<(\d+(?:[.,]\d+)?)", normalized)
    if m:
        return {"kind": "lt", "max": float(m.group(1).replace(",", "."))}

    m = re.match(r"^>(\d+(?:[.,]\d+)?)", normalized)
    if m:
        return {"kind": "gt", "min": float(m.group(1).replace(",", "."))}

    m = re.match(r"^(\d+(?:[.,]\d+)?)\+$", normalized)
    if m:
        return {"kind": "ge", "min": float(m.group(1).replace(",", "."))}

    m = re.match(r"^(\d+(?:[.,]\d+)?)-(\d+(?:[.,]\d+)?)", normalized)
    if m:
        return {
            "kind": "range",
            "min": float(m.group(1).replace(",", ".")),
            "max": float(m.group(2).replace(",", ".")),
        }

    return None


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _localized_text(value: Any, language: str, fallback: str = "") -> str:
    return localize_text(value, language, fallback)
