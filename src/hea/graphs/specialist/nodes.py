from __future__ import annotations

import json
import re
from typing import Any

from hea.shared.authoring_models import CriticReview, EditOperation, PendingProposal
from hea.shared.authoring_pipeline import (
    apply_proposal_to_draft,
    compile_questionnaire_spec,
    critic_review_spec,
    detailed_diff_summary,
    draft_to_spec,
    diff_summary,
    plan_edit_operation,
    proposal_to_spec,
    proposal_summary,
    review_to_text,
    spec_to_draft,
)
from hea.shared.drafts import (
    list_specialist_draft_versions,
    load_specialist_draft_version,
    log_specialist_audit_event,
    save_specialist_draft,
    save_specialist_draft_version,
)
from hea.shared.model_router import controller_client, extraction_client
from hea.shared.models import compile_graph_from_draft, default_draft, merge_dicts
from hea.shared.noisy_text import extract_candidate_update
from hea.shared.registry import upsert_graph
from hea.shared.runtime import infer_turn_language
from hea.shared.scaffold_registry import get_scaffold, infer_scaffold_framework, infer_scaffold_topic, looks_like_findrisk_questionnaire


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _detect_language(message: str) -> str:
    return "ru" if any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in message) else "en"


def _detect_language_switch(message: str) -> str | None:
    low = _normalize(message)
    if "на русском" in low or "по-русски" in low or "по русски" in low:
        return "ru"
    if "in english" in low or "speak english" in low or low == "english":
        return "en"
    return None


def _looks_like_yes(message: str) -> bool:
    low = _normalize(message)
    if low in {"да", "ок", "окей", "давай", "хорошо", "применяй", "примени", "yes", "ok", "apply", "go ahead", "применить"}:
        return True
    return any(token in low for token in {"подтвер", "подверж", "confirm", "approve", "создай черновик", "create draft"})


def _looks_like_no(message: str) -> bool:
    return _normalize(message) in {"нет", "не надо", "не применяй", "stop", "no", "cancel", "later"}


def _looks_like_review_help_request(message: str) -> bool:
    low = _normalize(message)
    return any(
        token in low
        for token in {
            "как решить",
            "как исправить",
            "помоги",
            "что делать дальше",
            "что дальше",
            "how to fix",
            "how do i fix",
            "help me",
            "what should i do next",
        }
    )


def _looks_like_smalltalk(message: str) -> bool:
    low = _normalize(message)
    return low in {"эй", "ей", "hey", "yo", "ау", "ага"} or len(low) <= 2


def _contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _strip_internal_meta(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not key.startswith("_")}


def _proposal_meta(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("_proposal_meta") or {}
    return meta if isinstance(meta, dict) else {}


def _has_meaningful_update(update: dict[str, Any]) -> bool:
    understood = update.get("understood") or {}
    return any(
        [
            bool(understood.get("topic")),
            bool(understood.get("artifact_type")),
            bool(update.get("candidate_questions")),
            bool(update.get("candidate_scoring_rules")),
            bool(update.get("candidate_risk_bands")),
            bool(update.get("candidate_anamnesis_sections")),
            bool(update.get("candidate_diagnostic_inputs")),
            bool(update.get("candidate_rule_nodes")),
        ]
    )


def _draft_has_meaningful_content(draft: dict[str, Any] | None) -> bool:
    draft = draft or {}
    understood = draft.get("understood") or {}
    return any(
        [
            bool(understood.get("topic")),
            bool(understood.get("artifact_type") and understood.get("artifact_type") != "questionnaire"),
            bool(draft.get("candidate_questions")),
            bool(draft.get("candidate_scoring_rules")),
            bool(draft.get("candidate_risk_bands")),
            bool(draft.get("candidate_anamnesis_sections")),
            bool(draft.get("candidate_diagnostic_inputs")),
            bool(draft.get("candidate_rule_nodes")),
        ]
    )


def _extract_direct_update(message: str, current_draft: dict[str, Any]) -> dict[str, Any]:
    low = _normalize(message)
    update: dict[str, Any] = {}

    m = re.search(r"^(?:topic|тема)\s*[:\-]?\s+(.+)$", low)
    if m:
        topic = infer_scaffold_topic(m.group(1))
        framework = infer_scaffold_framework(m.group(1))
        if topic:
            update = merge_dicts(update, get_scaffold(topic, framework))
            understood = dict(update.get("understood") or {})
            understood["description"] = message[:300]
            if framework:
                understood["framework"] = framework
            update["understood"] = understood
            return update

    topic = infer_scaffold_topic(message)
    framework = infer_scaffold_framework(message)
    if topic in {"diabetes", "sleep", "stress"}:
        update = merge_dicts(update, get_scaffold(topic, framework))
        understood = dict(update.get("understood") or {})
        understood["description"] = message[:300]
        if framework:
            understood["framework"] = framework
        update["understood"] = understood
        return update

    if len(low) > 40:
        topic_from_current = (current_draft.get("understood") or {}).get("topic")
        topic = infer_scaffold_topic(topic_from_current or message)
        framework = infer_scaffold_framework(message) or (current_draft.get("understood") or {}).get("framework")
        if topic:
            template = get_scaffold(topic, framework)
            update = merge_dicts(update, template)
            understood = dict(update.get("understood") or {})
            understood["topic"] = topic
            understood["description"] = message[:300]
            if framework:
                understood["framework"] = framework
            update["understood"] = understood
            return update

    return update


def _looks_like_detailed_draft_request(message: str) -> bool:
    low = _normalize(message)
    return _contains_any(low, ["драфт подробно", "show draft detailed", "show detailed draft", "подробный драфт"])


def _looks_like_question_source_request(message: str) -> bool:
    low = _normalize(message)
    return _contains_any(low, ["откуда ты взял вопросы", "откуда вопросы", "почему такие вопросы", "where did the questions come from"])


def _looks_like_direct_build_request(message: str) -> bool:
    low = _normalize(message)
    prefixes = ["создай ", "собери ", "сгенерируй ", "добавь ", "обнови ", "внеси ", "примени ", "generate ", "create ", "apply ", "update "]
    return any(low.startswith(prefix) for prefix in prefixes) or "в драфт" in low or "черновик" in low


def _looks_like_build_material(message: str) -> bool:
    low = _normalize(message)
    if "\n" in message and any(line.strip().startswith(("-", "*")) for line in message.splitlines()):
        return True
    if re.search(r"(?m)^\s*\d+[\.)]\s+", message):
        return True
    if len(message.strip()) >= 180:
        return True
    return _contains_any(
        low,
        [
            "guideline",
            "score",
            "scoring",
            "risk band",
            "risk bands",
            "вопрос",
            "шкала",
            "скоринг",
            "риски",
            "анамнез",
            "сценарий",
            "question",
            "questions",
        ],
    )


def _looks_like_goal_statement(message: str) -> bool:
    low = _normalize(message)
    return _contains_any(
        low,
        [
            "я хочу собрать",
            "хочу собрать",
            "хочу сделать",
            "мы собираем",
            "нужен сценарий",
            "тема:",
            "topic:",
            "findrisk",
            "диабет",
            "stress",
            "sleep",
            "assessment",
        ],
    )


async def _generate_candidate_update(message: str, current_draft: dict[str, Any]) -> dict[str, Any]:
    direct_update = _extract_direct_update(message, current_draft)
    noisy_update = extract_candidate_update(message, current_draft)

    extracted: dict[str, Any] = {}
    if _looks_like_build_material(message) or bool(direct_update):
        llm = extraction_client()
        extracted_raw = await llm.complete_json(
            system_prompt=(
                "Extract structured draft fields for an assessment graph. "
                "Return strict JSON with keys: understood, candidate_questions, "
                "candidate_scoring_rules, candidate_risk_bands, candidate_report_requirements, "
                "candidate_safety_requirements, missing_fields."
            ),
            user_prompt=json.dumps(
                {
                    "language": _detect_language(message),
                    "current_draft": current_draft,
                    "specialist_message": message,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        if isinstance(extracted_raw, dict):
            extracted = extracted_raw

    merged_update = merge_dicts(extracted, noisy_update)
    merged_update = merge_dicts(merged_update, direct_update)
    return merged_update


def _show_preview_text(draft: dict[str, Any], language: str) -> str:
    understood = draft.get("understood", {}) or {}
    artifact_type = understood.get("artifact_type") or "questionnaire"
    questions = draft.get("candidate_questions", []) or []
    scoring = draft.get("candidate_scoring_rules", {}) or {}
    risks = draft.get("candidate_risk_bands", []) or []
    anamnesis_sections = draft.get("candidate_anamnesis_sections", []) or []
    rule_nodes = draft.get("candidate_rule_nodes", []) or []
    if not any([understood, questions, scoring, risks, anamnesis_sections, rule_nodes]):
        return "Черновик пока пуст." if language == "ru" else "The draft is empty so far."

    framework = understood.get("framework")
    if language == "ru":
        lines = [
            "Текущий draft:",
            f"- Artifact type: {artifact_type}",
            f"- Topic: {understood.get('topic')}",
            f"- Framework: {framework or '—'}",
            f"- Description: {understood.get('description')}",
            f"- Questions: {len(questions)}",
            f"- Anamnesis sections: {len(anamnesis_sections)}",
            f"- Rule nodes: {len(rule_nodes)}",
            f"- Has scoring: {'yes' if bool(scoring) else 'no'}",
            f"- Risk bands: {len(risks)}",
        ]
        return "\n".join(lines)

    lines = [
        "Current draft:",
        f"- Artifact type: {artifact_type}",
        f"- Topic: {understood.get('topic')}",
        f"- Framework: {framework or '—'}",
        f"- Description: {understood.get('description')}",
        f"- Questions: {len(questions)}",
        f"- Anamnesis sections: {len(anamnesis_sections)}",
        f"- Rule nodes: {len(rule_nodes)}",
        f"- Has scoring: {'yes' if bool(scoring) else 'no'}",
        f"- Risk bands: {len(risks)}",
    ]
    return "\n".join(lines)


def _render_question_sources(questions: list[dict[str, Any]], language: str) -> str:
    if not questions:
        return "Источники вопросов пока не определены." if language == "ru" else "Question sources are not defined yet."

    lines = ["Источники вопросов:" if language == "ru" else "Question sources:"]
    for idx, question in enumerate(questions, start=1):
        source = question.get("source") or "unknown"
        lines.append(f"{idx}. {question.get('text', '—')} [{source}]")
    return "\n".join(lines)


def _show_detailed_draft_text(draft: dict[str, Any], language: str) -> str:
    understood = draft.get("understood", {}) or {}
    artifact_type = understood.get("artifact_type") or "questionnaire"
    questions = draft.get("candidate_questions", []) or []
    scoring = draft.get("candidate_scoring_rules", {}) or {}
    risks = draft.get("candidate_risk_bands", []) or []
    anamnesis_sections = draft.get("candidate_anamnesis_sections", []) or []
    diagnostic_inputs = draft.get("candidate_diagnostic_inputs", []) or []
    rule_nodes = draft.get("candidate_rule_nodes", []) or []
    if not any([understood, questions, scoring, risks, anamnesis_sections, diagnostic_inputs, rule_nodes]):
        return "Подробный draft пока пуст." if language == "ru" else "There is no detailed draft yet."

    lines = [
        "Подробный draft:" if language == "ru" else "Detailed draft:",
        f"Artifact type: {artifact_type}",
        f"Topic: {understood.get('topic') or '—'}",
        f"Framework: {understood.get('framework') or '—'}",
        f"Description: {understood.get('description') or '—'}",
        "",
        "Questions:" if language == "en" else "Questions:",
    ]
    if questions:
        for idx, question in enumerate(questions, start=1):
            options = ", ".join(str(option.get("label")) for option in question.get("options", []))
            source = question.get("source") or understood.get("source_summary") or "unknown"
            lines.append(f"{idx}. {question.get('text', '—')}")
            lines.append(f"   options: {options or '—'}")
            lines.append(f"   source: {source}")
            if question.get("source_line_range"):
                lines.append(f"   lines: {question.get('source_line_range')}")
            if question.get("source_excerpt"):
                lines.append(f"   excerpt: {question.get('source_excerpt')}")
    else:
        lines.append("—")

    if anamnesis_sections:
        lines.extend(["", "Anamnesis sections:"])
        for idx, section in enumerate(anamnesis_sections, start=1):
            lines.append(f"{idx}. {section.get('title', '—')}")
            lines.append(f"   goal: {section.get('goal') or '—'}")
            lines.append(f"   questions: {len(section.get('questions') or [])}")
            if section.get("source_excerpt"):
                lines.append(f"   excerpt: {section.get('source_excerpt')}")

    if diagnostic_inputs or rule_nodes:
        lines.extend(["", "Clinical rule graph:"])
        if diagnostic_inputs:
            lines.append("Inputs: " + ", ".join(str(item) for item in diagnostic_inputs))
        for idx, node in enumerate(rule_nodes, start=1):
            lines.append(f"{idx}. {node.get('label', '—')}")
            lines.append(f"   condition: {node.get('condition') or '—'}")
            lines.append(f"   outcome: {node.get('outcome') or '—'}")
            if node.get("source_excerpt"):
                lines.append(f"   excerpt: {node.get('source_excerpt')}")

    lines.extend(
        [
            "",
            "Scoring:",
            json.dumps(scoring, ensure_ascii=False, indent=2) if scoring else "—",
            "",
            "Risk bands:",
            json.dumps(risks, ensure_ascii=False, indent=2) if risks else "—",
            "",
            _render_question_sources(questions, language),
        ]
    )
    return "\n".join(lines)


def _show_questions_text(draft: dict[str, Any], language: str) -> str:
    questions = draft.get("candidate_questions", []) or []
    if not questions:
        for section in draft.get("candidate_anamnesis_sections", []) or []:
            questions.extend(section.get("questions") or [])
    if not questions:
        return "В draft пока нет вопросов." if language == "ru" else "There are no questions in the draft yet."
    prefix = "Вопросы:" if language == "ru" else "Questions:"
    return prefix + "\n" + "\n".join(f"{idx}. {q.get('text', '—')}" for idx, q in enumerate(questions, start=1))


def _show_versions_text(conversation_id: str, language: str) -> str:
    versions = list_specialist_draft_versions(conversation_id, limit=5)
    if not versions:
        return "Версий draft пока нет." if language == "ru" else "There are no draft versions yet."
    lines = ["Последние версии draft:" if language == "ru" else "Recent draft versions:"]
    for item in versions:
        lines.append(f"- v{item['version_id']} | {item['created_at']} | {item.get('note') or 'snapshot'}")
    return "\n".join(lines)


def _effective_apply_operation(state: dict, proposal: PendingProposal) -> EditOperation:
    raw = state.get("edit_operation")
    if isinstance(raw, dict):
        try:
            operation = EditOperation.model_validate(raw)
            if operation.intent_type in {"apply_questions_only", "apply_risks_only", "apply_sections_only", "apply_rules_only"}:
                return operation
        except Exception:
            pass
    return proposal.operation


def _proposal_summary(proposal: dict[str, Any]) -> tuple[str | None, str | None, int, bool, int]:
    understood = proposal.get("understood", {}) or {}
    questions = proposal.get("candidate_questions", []) or []
    scoring = proposal.get("candidate_scoring_rules", {}) or {}
    risks = proposal.get("candidate_risk_bands", []) or []
    return understood.get("topic"), understood.get("framework"), len(questions), bool(scoring), len(risks)


def _hydrate_questionnaire_draft_from_scaffold(draft: dict[str, Any]) -> dict[str, Any]:
    draft = dict(draft or default_draft())
    understood = draft.get("understood") or {}
    artifact_type = understood.get("artifact_type") or "questionnaire"
    topic = understood.get("topic")
    framework = understood.get("framework")
    questions = draft.get("candidate_questions") or []
    if artifact_type != "questionnaire" or not questions:
        return draft
    if looks_like_findrisk_questionnaire(topic, framework, questions):
        framework = "findrisk"
        understood["framework"] = framework
        draft["understood"] = understood
    if framework not in {"burnout", "findrisk"}:
        return draft
    scaffold = get_scaffold(topic, framework)
    if not scaffold:
        return draft
    if not draft.get("candidate_risk_bands"):
        draft["candidate_risk_bands"] = list(scaffold.get("candidate_risk_bands") or [])
    if not draft.get("candidate_report_requirements"):
        draft["candidate_report_requirements"] = list(scaffold.get("candidate_report_requirements") or [])
    return draft


def _help_text(language: str) -> str:
    if language == "ru":
        return (
            "Я помогаю собирать клинические graph-артефакты для patient bot.\n\n"
            "Сейчас доступны 3 типа graph:\n"
            "1. questionnaire\n"
            "- scored questionnaires и screening scales\n"
            "- что прислать: вопросы, варианты ответов, баллы, risk bands, интерпретацию\n\n"
            "2. anamnesis_flow\n"
            "- сценарии сбора анамнеза\n"
            "- что прислать: секции, вопросы, branching cues, red flags\n\n"
            "3. clinical_rule_graph\n"
            "- rule-based схемы ранней диагностики или triage\n"
            "- что прислать: диагностические входы, if/then правила, thresholds, outcomes\n\n"
            "Рекомендуемый workflow:\n"
            "1. описать цель и тип graph\n"
            "2. прислать source text или структуру\n"
            "3. посмотреть proposal / diff\n"
            "4. `примени предложение`\n"
            "5. при необходимости добавить risk bands или правила\n"
            "6. `compile`\n"
            "7. `publish`\n\n"
            "Полезные команды:\n"
            "- show draft\n"
            "- show diff\n"
            "- show versions\n"
            "- rollback v3\n"
            "- show detailed draft\n"
            "- show questions\n"
            "- show scoring\n"
            "- show risks\n"
            "- compile\n"
            "- publish"
        )
    return (
        "I help assemble clinical graph artifacts for the patient bot.\n\n"
        "Supported graph types:\n"
        "1. questionnaire\n"
        "- scored questionnaires and screening scales\n"
        "- send: questions, options, scores, risk bands, interpretation\n\n"
        "2. anamnesis_flow\n"
        "- history-taking flows\n"
        "- send: sections, questions, branching cues, red flags\n\n"
        "3. clinical_rule_graph\n"
        "- rule-based early-detection or triage logic\n"
        "- send: diagnostic inputs, if/then rules, thresholds, outcomes\n\n"
        "Recommended workflow:\n"
        "1. describe the goal and graph type\n"
        "2. send source text or structure\n"
        "3. review proposal / diff\n"
        "4. `apply proposal`\n"
        "5. add risk bands or rules if needed\n"
        "6. `compile`\n"
        "7. `publish`\n\n"
        "Useful commands:\n"
        "- show draft\n"
        "- show diff\n"
        "- show versions\n"
        "- rollback v3\n"
        "- show detailed draft\n"
        "- show questions\n"
        "- show scoring\n"
        "- show risks\n"
        "- compile\n"
        "- publish"
    )


def _append_next_step_hint(reply: str, state: dict, language: str) -> str:
    pending = state.get("pending_proposal")
    compile_result = state.get("compile_result") or {}
    publish_result = state.get("publish_result") or {}
    draft = state.get("draft") or default_draft()
    understood = draft.get("understood") or {}
    artifact_type = understood.get("artifact_type") or "questionnaire"
    questions = draft.get("candidate_questions") or []
    scoring = draft.get("candidate_scoring_rules") or {}
    risks = draft.get("candidate_risk_bands") or []
    sections = draft.get("candidate_anamnesis_sections") or []
    rule_nodes = draft.get("candidate_rule_nodes") or []

    hint: str | None = None
    if isinstance(pending, dict):
        hint = (
            "Подсказка: сейчас есть подготовленное предложение. Следующий шаг: `примени предложение` или сначала `show diff`."
            if language == "ru"
            else "Hint: there is a pending proposal. Next step: `apply proposal` or review it first with `show diff`."
        )
    elif compile_result.get("status") == "compiled" and not publish_result.get("status"):
        hint = (
            "Подсказка: graph уже скомпилирован. Следующий шаг: `publish`, чтобы он стал доступен patient bot."
            if language == "ru"
            else "Hint: the graph is already compiled. Next step: `publish` to make it available to the patient bot."
        )
    elif artifact_type == "questionnaire" and questions and scoring and not risks:
        hint = (
            "Подсказка: для questionnaire не хватает risk bands. Добавьте интерпретацию суммы баллов или диапазоны риска, затем `compile`."
            if language == "ru"
            else "Hint: the questionnaire is missing risk bands. Add score interpretation or risk ranges, then run `compile`."
        )
    elif artifact_type == "questionnaire" and questions and risks:
        hint = (
            "Подсказка: questionnaire выглядит почти готовым. Следующий шаг: `compile`, потом `publish`."
            if language == "ru"
            else "Hint: the questionnaire looks close to ready. Next step: `compile`, then `publish`."
        )
    elif artifact_type == "anamnesis_flow" and sections:
        hint = (
            "Подсказка: у anamnesis_flow уже есть секции. Проверьте вопросы и red flags, затем `compile`."
            if language == "ru"
            else "Hint: the anamnesis flow already has sections. Review questions and red flags, then `compile`."
        )
    elif artifact_type == "clinical_rule_graph" and rule_nodes:
        hint = (
            "Подсказка: у clinical_rule_graph уже есть rule nodes. Проверьте thresholds и outcomes, затем `compile`."
            if language == "ru"
            else "Hint: the clinical rule graph already has rule nodes. Review thresholds and outcomes, then `compile`."
        )
    elif not any([questions, sections, rule_nodes]):
        hint = (
            "Подсказка: сначала выберите тип graph и пришлите структуру. Например: questionnaire с вопросами и баллами, anamnesis_flow с секциями, или clinical_rule_graph с if/then правилами."
            if language == "ru"
            else "Hint: first choose a graph type and send structure. For example: a questionnaire with scored questions, an anamnesis flow with sections, or a clinical rule graph with if/then rules."
        )

    if not hint or hint in reply:
        return reply
    return reply + "\n\n" + hint


def _default_analyst_decision(language: str) -> dict[str, Any]:
    return {
        "next_action": "DISCUSS",
        "should_prepare_proposal": False,
        "should_apply_pending": False,
        "follow_up_question": "",
        "action_rationale": "default fallback",
        "confidence": 0.5,
        "recognized_topic": None,
        "language": language,
    }


def _sanitize_analyst_decision(raw: dict[str, Any] | None, language: str) -> dict[str, Any]:
    decision = _default_analyst_decision(language)
    if not isinstance(raw, dict):
        return decision

    valid_actions = {
        "DISCUSS",
        "UPDATE_DRAFT",
        "SHOW_DIFF",
        "SHOW_VERSIONS",
        "ROLLBACK_DRAFT",
        "SHOW_PREVIEW",
        "SHOW_DETAILED_DRAFT",
        "SHOW_QUESTIONS",
        "SHOW_SCORING",
        "SHOW_RISKS",
        "EXPLAIN_QUESTION_SOURCE",
        "APPLY_PENDING_PROPOSAL",
        "COMPILE",
        "PUBLISH",
        "SHOW_HELP",
    }
    next_action = str(raw.get("next_action") or "").upper()
    if next_action in valid_actions:
        decision["next_action"] = next_action

    decision["should_prepare_proposal"] = bool(raw.get("should_prepare_proposal"))
    decision["should_apply_pending"] = bool(raw.get("should_apply_pending"))
    decision["follow_up_question"] = str(raw.get("follow_up_question") or "")
    decision["action_rationale"] = str(raw.get("action_rationale") or decision["action_rationale"])
    try:
        decision["confidence"] = float(raw.get("confidence", decision["confidence"]))
    except Exception:
        pass
    recognized_topic = raw.get("recognized_topic")
    if isinstance(recognized_topic, str) and recognized_topic.strip():
        decision["recognized_topic"] = recognized_topic.strip()
    decision["language"] = language
    return decision


async def _analyze_specialist_turn(state: dict, language: str) -> dict[str, Any]:
    message = str(state.get("user_message") or "")
    payload = {
        "analysis_mode": "specialist_turn",
        "language": language,
        "specialist_message": message,
        "current_draft": state.get("draft") or default_draft(),
        "pending_proposal_exists": bool(state.get("pending_proposal")),
    }
    analyst = controller_client()
    raw = await analyst.complete_json(
        system_prompt=(
            "You are a conversation analyst for a specialist-facing assessment authoring bot. "
            "Return strict JSON with keys: next_action, should_prepare_proposal, should_apply_pending, "
            "follow_up_question, action_rationale, confidence, recognized_topic. "
            "Valid next_action values: DISCUSS, UPDATE_DRAFT, SHOW_PREVIEW, SHOW_DETAILED_DRAFT, "
            "SHOW_QUESTIONS, SHOW_SCORING, SHOW_RISKS, EXPLAIN_QUESTION_SOURCE, APPLY_PENDING_PROPOSAL, COMPILE, PUBLISH, SHOW_HELP. "
            "Prefer DISCUSS for ambiguous free-form messages. Use UPDATE_DRAFT only for explicit build/update requests."
        ),
        user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
    )
    return _sanitize_analyst_decision(raw, language)


def _discussion_reply(message: str, state: dict, language: str) -> str:
    draft = state.get("draft") or default_draft()
    topic = (draft.get("understood") or {}).get("topic")
    if _looks_like_smalltalk(message):
        return (
            "Я не буду менять draft по такой короткой реплике. Можете описать цель assessment, прислать source text или попросить показать текущий draft."
            if language == "ru"
            else "I will not change the draft based on such a short message. You can describe the assessment goal, send source text, or ask to see the current draft."
        )

    if topic:
        return (
            f"Понял. Сейчас у нас в работе тема {topic}. Я не менял draft автоматически. "
            f"Можете описать, какие вопросы, логика скоринга или риск-бэнды вам нужны, и я подготовлю предложение перед применением."
            if language == "ru"
            else f"Understood. We are currently working on topic {topic}. I did not change the draft automatically. "
                 f"You can describe the questions, scoring logic, or risk bands you want, and I will prepare a proposal before applying it."
        )

    return (
        "Пока у меня недостаточно структуры, чтобы безопасно менять draft. Опишите тему, желаемые вопросы, скоринг или пришлите guideline, и я сначала предложу черновик."
        if language == "ru"
        else "I do not have enough structure to change the draft safely yet. Describe the topic, desired questions, scoring, or send a guideline, and I will propose a draft first."
    )


def _proposal_reply(message: str, proposal: dict[str, Any], language: str) -> str:
    topic, framework, question_count, has_scoring, risk_count = _proposal_summary(proposal)
    meta = _proposal_meta(proposal)
    source_summary = meta.get("question_source_summary") or (proposal.get("understood") or {}).get("source_summary") or "message analysis"

    if language == "ru":
        lines = [
            f"Понял ваш запрос: {message.strip()}",
            "Я подготовил предложение, но пока НЕ применял его к draft.",
            f"- Topic: {topic or '—'}",
            f"- Framework: {framework or '—'}",
            f"- Вопросов в предложении: {question_count}",
            f"- Скоринг задан: {'yes' if has_scoring else 'no'}",
            f"- Risk bands: {risk_count}",
            f"- Источник вопросов: {source_summary}",
            "",
            "Если хотите применить это предложение, напишите: `примени предложение`, `создай черновик` или просто `да`.",
            "Если хотите сначала обсудить структуру, просто продолжайте писать в свободной форме.",
        ]
        return "\n".join(lines)

    lines = [
        f"I understood your request as: {message.strip()}",
        "I prepared a proposal, but I have NOT applied it to the draft yet.",
        f"- Topic: {topic or '—'}",
        f"- Framework: {framework or '—'}",
        f"- Proposed questions: {question_count}",
        f"- Scoring present: {'yes' if has_scoring else 'no'}",
        f"- Risk bands: {risk_count}",
        f"- Question source: {source_summary}",
        "",
        "If you want to apply this proposal, reply with `apply proposal`, `create draft`, or simply `yes`.",
        "If you want to discuss the structure first, just continue in free form.",
    ]
    return "\n".join(lines)


async def route_specialist_message(state: dict) -> dict:
    message = str(state.get("user_message") or "")
    low = _normalize(message)

    language_switch = _detect_language_switch(message)
    current_language = str(state.get("language") or "en")
    language = language_switch or infer_turn_language(message, current_language or _detect_language(message))

    if low in {"/start", "start", "привет", "hello", "hi"}:
        return {"language": language, "next_action": "RESET_AND_HELP"}

    if language_switch:
        return {"language": language, "next_action": "ACK_LANGUAGE"}

    if state.get("pending_proposal") and _looks_like_yes(message):
        return {"language": language, "next_action": "APPLY_PENDING_PROPOSAL"}

    if low in {"help", "show help", "помощь", "что умеешь", "какие графы есть?", "какие графы есть", "какие типы графов есть"}:
        return {"language": language, "next_action": "SHOW_HELP"}
    if low in {"compile", "компилируй", "скомпилируй"}:
        return {"language": language, "next_action": "COMPILE"}
    if low in {"publish", "опубликуй", "публикуй"}:
        return {"language": language, "next_action": "PUBLISH"}
    if low in {"show draft", "покажи драфт", "покажи текущий драфт", "покажи мне текущий стресс"}:
        return {"language": language, "next_action": "SHOW_DETAILED_DRAFT"}

    if low in {"show diff", "покажи diff", "покажи изменения", "show changes"}:
        return {"language": language, "next_action": "SHOW_DIFF"}
    if low in {"show versions", "покажи версии", "версии"}:
        return {"language": language, "next_action": "SHOW_VERSIONS"}
    if low in {"примени только вопросы", "apply questions only"}:
        return {"language": language, "next_action": "APPLY_PENDING_PROPOSAL", "edit_operation": EditOperation(intent_type="apply_questions_only", target_section="questions", requires_confirmation=False).model_dump(mode="json")}
    if low in {"примени только риски", "apply risks only"}:
        return {"language": language, "next_action": "APPLY_PENDING_PROPOSAL", "edit_operation": EditOperation(intent_type="apply_risks_only", target_section="risk_bands", requires_confirmation=False).model_dump(mode="json")}
    if low in {"примени только секции", "apply sections only"}:
        return {"language": language, "next_action": "APPLY_PENDING_PROPOSAL", "edit_operation": EditOperation(intent_type="apply_sections_only", target_section="anamnesis_sections", requires_confirmation=False).model_dump(mode="json")}
    if low in {"примени только правила", "apply rules only"}:
        return {"language": language, "next_action": "APPLY_PENDING_PROPOSAL", "edit_operation": EditOperation(intent_type="apply_rules_only", target_section="rule_nodes", requires_confirmation=False).model_dump(mode="json")}
    rollback_match = re.search(r"(?:rollback|откати(?:\s+на)?|верни\s+на)\s*v?(\d+)", low)
    if rollback_match:
        return {
            "language": language,
            "next_action": "ROLLBACK_DRAFT",
            "edit_operation": EditOperation(intent_type="rollback_draft", rollback_version_id=int(rollback_match.group(1))).model_dump(mode="json"),
        }

    if _looks_like_build_material(message):
        return {
            "language": language,
            "next_action": "DISCUSS",
            "analyst_decision": {
                "next_action": "DISCUSS",
                "should_prepare_proposal": True,
                "should_apply_pending": False,
                "follow_up_question": "",
                "action_rationale": "direct build-material shortcut",
                "confidence": 0.99,
                "recognized_topic": infer_scaffold_topic(message),
                "language": language,
            },
        }

    analyst_decision = await _analyze_specialist_turn(state, language)
    return {
        "language": language,
        "next_action": analyst_decision["next_action"],
        "analyst_decision": analyst_decision,
    }


async def reset_and_help(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    draft = default_draft()
    reply = _help_text(language)
    return {"draft": draft, "pending_proposal": None, "compile_result": None, "publish_result": None, "assistant_reply": reply}


async def ack_language(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {
        "assistant_reply": (
            "Хорошо, продолжим по-русски. Опишите идею assessment в свободной форме или пришлите source text."
            if language == "ru"
            else "Okay, we will continue in English. Describe the assessment idea in free form or send source text."
        )
    }


async def show_help(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    return {"assistant_reply": _append_next_step_hint(_help_text(language), state, language)}


async def discuss_specialist_goal(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    message = str(state.get("user_message") or "")
    current = state.get("draft") or default_draft()
    pending = state.get("pending_proposal")
    analyst_decision = state.get("analyst_decision") or _default_analyst_decision(language)
    if not _draft_has_meaningful_content(current):
        pending_spec = proposal_to_spec(pending)
        if pending_spec is not None:
            current = spec_to_draft(pending_spec)
    operation = await plan_edit_operation(message, current, language, bool(pending))

    if isinstance(pending, dict) and _looks_like_review_help_request(message):
        try:
            proposal = PendingProposal.model_validate(pending)
            review_text = review_to_text(proposal.review, language)
        except Exception:
            proposal = None
            review_text = ""
        if proposal is not None and (proposal.review.findings or proposal.review.missing_information):
            guidance = (
                "Чтобы снять эти замечания, пришлите недостающие элементы как отдельное обновление. "
                "Например: risk bands / интерпретацию суммы баллов, затем снова `примени предложение`. "
                "После этого выполните `compile`, затем `publish`."
                if language == "ru"
                else "To resolve these findings, send the missing elements as a separate update. "
                     "For example: risk bands / score interpretation, then apply the proposal again. "
                     "After that run `compile`, then `publish`."
            )
            return {
                "analyst_decision": analyst_decision,
                "edit_operation": operation.model_dump(mode="json"),
                "assistant_reply": _append_next_step_hint(review_text + "\n\n" + guidance, state, language),
            }

    if pending and _looks_like_no(message):
        return {
            "pending_proposal": None,
            "analyst_decision": analyst_decision,
            "edit_operation": operation.model_dump(mode="json"),
            "assistant_reply": (
                "Хорошо, не буду применять последнее предложение. Продолжайте описывать нужную структуру в свободной форме."
                if language == "ru"
                else "Okay, I will not apply the last proposal. Continue describing the structure you need in free form."
            ),
        }

    if bool(analyst_decision.get("should_prepare_proposal")):
        current_spec = draft_to_spec(current)
        spec = await compile_questionnaire_spec(message, current, operation, language)
        review = await critic_review_spec(message, spec, operation, language)
        proposal = PendingProposal(operation=operation, spec=spec, review=review, source_message=message)
        proposal_reply = proposal_summary(proposal, language)
        proposal_reply += "\n\n" + detailed_diff_summary(current_spec, spec, language)
        follow_up_question = str(analyst_decision.get("follow_up_question") or "").strip()
        if follow_up_question:
            proposal_reply = proposal_reply + "\n\n" + follow_up_question
        proposal_reply += (
            "\n\nЕсли хотите применить это изменение, напишите `примени предложение` или `да`."
            if language == "ru"
            else "\n\nIf you want to apply this change, reply with `apply proposal` or `yes`."
        )
        proposal_reply = _append_next_step_hint(proposal_reply, {**state, "pending_proposal": proposal.model_dump(mode="json")}, language)
        return {
            "pending_proposal": proposal.model_dump(mode="json"),
            "analyst_decision": analyst_decision,
            "edit_operation": operation.model_dump(mode="json"),
            "critic_review": review.model_dump(mode="json"),
            "assistant_reply": proposal_reply,
        }

    reply = _discussion_reply(message, state, language)
    follow_up_question = str(analyst_decision.get("follow_up_question") or "").strip()
    if follow_up_question and analyst_decision.get("confidence", 0.0) >= 0.6:
        reply = reply + "\n\n" + follow_up_question
    reply = _append_next_step_hint(reply, state, language)
    return {
        "analyst_decision": analyst_decision,
        "edit_operation": operation.model_dump(mode="json"),
        "assistant_reply": reply,
    }


async def apply_pending_proposal(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    current = state.get("draft") or default_draft()
    proposal_raw = state.get("pending_proposal")
    if not isinstance(proposal_raw, dict):
        return {
            "assistant_reply": (
                "Сейчас нет подготовленного предложения для применения. Опишите тему или структуру assessment, и я сначала соберу предложение."
                if language == "ru"
                else "There is no prepared proposal to apply right now. Describe the topic or structure, and I will prepare a proposal first."
            )
        }

    proposal = PendingProposal.model_validate(proposal_raw)
    effective_operation = _effective_apply_operation(state, proposal)
    if proposal.review.should_block_apply:
        return {
            "critic_review": proposal.review.model_dump(mode="json"),
            "assistant_reply": (
                "Я не применил предложение, потому что проверка нашла критические проблемы.\n\n" + review_to_text(proposal.review, language)
                if language == "ru"
                else "I did not apply the proposal because validation found critical issues.\n\n" + review_to_text(proposal.review, language)
            ),
        }

    conversation_id = str(state.get("conversation_id") or "unknown")
    draft = apply_proposal_to_draft(proposal.spec, effective_operation, current)
    draft = _hydrate_questionnaire_draft_from_scaffold(draft)
    version_id = save_specialist_draft_version(
        conversation_id,
        draft,
        operation=effective_operation.model_dump(mode="json"),
        note=f"apply:{effective_operation.intent_type}",
    )
    save_specialist_draft(conversation_id, draft)
    log_specialist_audit_event(
        conversation_id,
        "apply_pending_proposal",
        {
            "operation": effective_operation.model_dump(mode="json"),
            "version_id": version_id,
            "artifact_type": proposal.spec.artifact_type,
            "topic": proposal.spec.topic,
        },
    )
    return {
        "draft": draft,
        "pending_proposal": None,
        "critic_review": proposal.review.model_dump(mode="json"),
        "assistant_reply": _append_next_step_hint((
            f"Применил предложение к draft и сохранил версию v{version_id}.\n\n"
            + _show_preview_text(draft, language)
            + "\n\nГраф еще не доступен пациенту. Чтобы добавить его в библиотеку patient bot, выполните `compile`, затем `publish`."
            if language == "ru"
            else f"Applied the proposal to the draft and saved version v{version_id}.\n\n"
                 + _show_preview_text(draft, language)
                 + "\n\nThe graph is not available to the patient bot yet. Run `compile` and then `publish` to add it to the library."
        ), {"draft": draft, "pending_proposal": None}, language),
    }


async def update_draft(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    current = state.get("draft") or default_draft()
    user_message = str(state.get("user_message") or "")
    if not _draft_has_meaningful_content(current):
        pending_spec = proposal_to_spec(state.get("pending_proposal"))
        if pending_spec is not None:
            current = spec_to_draft(pending_spec)
    operation = await plan_edit_operation(user_message, current, language, bool(state.get("pending_proposal")))
    spec = await compile_questionnaire_spec(user_message, current, operation, language)
    review = await critic_review_spec(user_message, spec, operation, language)
    current_spec = draft_to_spec(current)
    if not spec.questions and operation.intent_type in {"replace_questions_from_text", "append_questions_from_text"}:
        return {
            "edit_operation": operation.model_dump(mode="json"),
            "assistant_reply": (
                "Я не увидел достаточно структуры, чтобы обновить draft. Можете прислать topic, список вопросов, scoring logic или guideline."
                if language == "ru"
                else "I did not see enough structure to update the draft. You can send a topic, a list of questions, scoring logic, or a guideline."
            )
        }

    proposal = PendingProposal(operation=operation, spec=spec, review=review, source_message=user_message)
    return {
        "pending_proposal": proposal.model_dump(mode="json"),
        "edit_operation": operation.model_dump(mode="json"),
        "critic_review": review.model_dump(mode="json"),
        "assistant_reply": _append_next_step_hint(proposal_summary(proposal, language)
        + "\n\n"
        + detailed_diff_summary(current_spec, spec, language)
        + (
            "\n\nЕсли хотите применить это изменение, напишите `примени предложение` или `да`."
            if language == "ru"
            else "\n\nIf you want to apply this change, reply with `apply proposal` or `yes`."
        ), {**state, "pending_proposal": proposal.model_dump(mode="json")}, language),
    }


async def show_preview(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    draft = state.get("draft") or default_draft()
    return {"assistant_reply": _append_next_step_hint(_show_preview_text(draft, language), state, language)}


async def show_diff(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    current = state.get("draft") or default_draft()
    proposal_raw = state.get("pending_proposal")
    if not isinstance(proposal_raw, dict):
        return {"assistant_reply": "Нет ожидающего proposal для diff." if language == "ru" else "There is no pending proposal to diff."}
    proposal = PendingProposal.model_validate(proposal_raw)
    return {"assistant_reply": detailed_diff_summary(draft_to_spec(current), proposal.spec, language)}


async def show_versions(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    conversation_id = str(state.get("conversation_id") or "unknown")
    return {"assistant_reply": _show_versions_text(conversation_id, language)}


async def rollback_draft(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    conversation_id = str(state.get("conversation_id") or "unknown")
    operation_raw = state.get("edit_operation") or {}
    try:
        operation = EditOperation.model_validate(operation_raw)
    except Exception:
        operation = EditOperation(intent_type="rollback_draft")
    version_id = operation.rollback_version_id
    if not version_id:
        return {"assistant_reply": "Не указана версия для rollback." if language == "ru" else "Rollback version is not specified."}
    draft = load_specialist_draft_version(conversation_id, version_id)
    if draft is None:
        return {"assistant_reply": f"Версия v{version_id} не найдена." if language == "ru" else f"Version v{version_id} was not found."}
    new_version_id = save_specialist_draft_version(
        conversation_id,
        draft,
        operation=operation.model_dump(mode="json"),
        note=f"rollback_to:{version_id}",
    )
    save_specialist_draft(conversation_id, draft)
    log_specialist_audit_event(conversation_id, "rollback_draft", {"requested_version_id": version_id, "new_version_id": new_version_id})
    return {
        "draft": draft,
        "assistant_reply": (
            f"Откатил draft к версии v{version_id} и сохранил новую версию v{new_version_id}.\n\n" + _show_preview_text(draft, language)
            if language == "ru"
            else f"Rolled the draft back to version v{version_id} and saved new version v{new_version_id}.\n\n" + _show_preview_text(draft, language)
        ),
    }


async def show_detailed_draft(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    draft = state.get("draft") or default_draft()
    if not any(draft.values()) and isinstance(state.get("pending_proposal"), dict):
        try:
            proposal = PendingProposal.model_validate(state["pending_proposal"])
            draft = spec_to_draft(proposal.spec)
        except Exception:
            pass
    return {"assistant_reply": _append_next_step_hint(_show_detailed_draft_text(draft, language), state, language)}


async def show_questions(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    draft = state.get("draft") or default_draft()
    return {"assistant_reply": _show_questions_text(draft, language)}


async def show_scoring(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    draft = state.get("draft") or default_draft()
    scoring = draft.get("candidate_scoring_rules", {}) or {}
    if not scoring:
        return {"assistant_reply": "Scoring logic пока не задана." if language == "ru" else "Scoring logic is not defined yet."}
    return {"assistant_reply": json.dumps(scoring, ensure_ascii=False, indent=2)}


async def show_risks(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    draft = state.get("draft") or default_draft()
    risks = draft.get("candidate_risk_bands", []) or []
    if not risks:
        return {"assistant_reply": "Risk bands пока не заданы." if language == "ru" else "Risk bands are not defined yet."}
    return {"assistant_reply": json.dumps(risks, ensure_ascii=False, indent=2)}


async def explain_question_source(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    draft = state.get("draft") or default_draft()
    questions = draft.get("candidate_questions", []) or []
    if not questions:
        for section in draft.get("candidate_anamnesis_sections", []) or []:
            questions.extend(section.get("questions") or [])
    if not questions and isinstance(state.get("pending_proposal"), dict):
        try:
            proposal = PendingProposal.model_validate(state["pending_proposal"])
            questions = [question.model_dump(mode="json") for question in proposal.spec.questions]
            if not questions:
                for section in proposal.spec.anamnesis_sections:
                    questions.extend(question.model_dump(mode="json") for question in section.questions)
        except Exception:
            questions = []
    return {"assistant_reply": _render_question_sources(questions, language)}


async def compile_draft(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    draft = _hydrate_questionnaire_draft_from_scaffold(state.get("draft") or default_draft())
    conversation_id = str(state.get("conversation_id") or "unknown")
    critic_review = state.get("critic_review") or {}
    if isinstance(critic_review, dict) and critic_review.get("should_block_apply"):
        return {
            "assistant_reply": (
                "Сначала исправьте критические замечания проверки, потом выполняйте compile.\n\n" + review_to_text(CriticReview.model_validate(critic_review), language)
                if language == "ru"
                else "Fix the critical validation findings before compile.\n\n" + review_to_text(CriticReview.model_validate(critic_review), language)
            )
        }
    result = compile_graph_from_draft(draft)
    if result["status"] != "compiled":
        reply = (
            "Draft пока не готов к compile:\n- " + "\n- ".join(result.get("feedback", []))
            if language == "ru"
            else "Draft is not compile-ready:\n- " + "\n- ".join(result.get("feedback", []))
        )
    else:
        reply = (
            f"Graph успешно скомпилирован. Graph ID: {result['graph_id']}\n\nТеперь выполните `publish`, чтобы граф стал доступен пациентскому боту."
            if language == "ru"
            else f"Graph compiled successfully. Graph ID: {result['graph_id']}\n\nRun `publish` to make it available to the patient bot."
        )
    log_specialist_audit_event(conversation_id, "compile_draft", {"status": result.get("status"), "feedback": result.get("feedback", []), "graph_id": result.get("graph_id")})
    return {"compile_result": result, "assistant_reply": _append_next_step_hint(reply, {**state, "compile_result": result}, language)}


async def publish_draft(state: dict) -> dict:
    language = str(state.get("language") or "ru")
    conversation_id = str(state.get("conversation_id") or "unknown")
    critic_review = state.get("critic_review") or {}
    if isinstance(critic_review, dict) and critic_review.get("should_block_apply"):
        return {
            "assistant_reply": (
                "Публикация заблокирована: в draft есть критические замечания проверки.\n\n" + review_to_text(CriticReview.model_validate(critic_review), language)
                if language == "ru"
                else "Publish is blocked because the draft still has critical validation findings.\n\n" + review_to_text(CriticReview.model_validate(critic_review), language)
            )
        }
    compile_result = state.get("compile_result")
    if not isinstance(compile_result, dict) or compile_result.get("status") != "compiled":
        return {"assistant_reply": "Сначала выполните compile." if language == "ru" else "Compile the draft first."}
    review = CriticReview.model_validate(critic_review) if isinstance(critic_review, dict) and critic_review else CriticReview()
    if review.findings or review.missing_information:
        return {
            "assistant_reply": (
                "Публикация заблокирована: сначала устраните замечания review и убедитесь, что draft подтвержден специалистом.\n\n" + review_to_text(review, language)
                if language == "ru"
                else "Publish is blocked until review findings are resolved and the draft is explicitly confirmed.\n\n" + review_to_text(review, language)
            )
        }
    graph = compile_result["graph"]
    upsert_graph(graph)
    log_specialist_audit_event(conversation_id, "publish_draft", {"graph_id": graph["graph_id"], "artifact_type": graph.get("artifact_type"), "topic": graph.get("topic")})
    return {
        "publish_result": {"graph_id": graph["graph_id"], "status": "published"},
        "assistant_reply": _append_next_step_hint((
            f"Graph опубликован. Graph ID: {graph['graph_id']}"
            if language == "ru"
            else f"Graph published. Graph ID: {graph['graph_id']}"
        ), {**state, "publish_result": {"graph_id": graph["graph_id"], "status": "published"}}, language),
    }
