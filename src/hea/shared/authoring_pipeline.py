from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from hea.shared.authoring_models import (
    AnamnesisSectionSpec,
    ClinicalRuleNodeSpec,
    CriticReview,
    EditOperation,
    PendingProposal,
    QuestionOptionSpec,
    QuestionnaireSpec,
    RiskBandSpec,
    ValidationFinding,
)
from hea.shared.model_router import controller_client, specialist_compiler_client, specialist_critic_client
from hea.shared.models import default_draft
from hea.shared.noisy_text import infer_artifact_type
from hea.shared.scaffold_registry import (
    get_scaffold,
    infer_scaffold_framework,
    infer_scaffold_topic,
    looks_like_findrisk_questionnaire,
)


def draft_to_spec(draft: dict[str, Any] | None) -> QuestionnaireSpec:
    draft = draft or default_draft()
    understood = draft.get("understood") or {}
    return QuestionnaireSpec(
        artifact_type=(understood.get("artifact_type") or "questionnaire"),
        topic=understood.get("topic"),
        framework=understood.get("framework"),
        title=understood.get("title"),
        description=understood.get("description"),
        questions=draft.get("candidate_questions") or [],
        scoring_method=(draft.get("candidate_scoring_rules") or {}).get("method"),
        risk_bands=draft.get("candidate_risk_bands") or [],
        anamnesis_sections=draft.get("candidate_anamnesis_sections") or [],
        red_flags=draft.get("candidate_red_flags") or [],
        assessment_output=draft.get("candidate_assessment_output"),
        report_requirements=draft.get("candidate_report_requirements") or [],
        diagnostic_inputs=draft.get("candidate_diagnostic_inputs") or [],
        rule_nodes=draft.get("candidate_rule_nodes") or [],
        conclusion_template=draft.get("candidate_conclusion_template"),
    )


def proposal_to_spec(proposal: dict[str, Any] | None) -> QuestionnaireSpec | None:
    if not isinstance(proposal, dict):
        return None
    try:
        pending = PendingProposal.model_validate(proposal)
    except ValidationError:
        return None
    return pending.spec


def spec_to_draft(spec: QuestionnaireSpec, base_draft: dict[str, Any] | None = None) -> dict[str, Any]:
    draft = dict(base_draft or default_draft())
    understood = dict(draft.get("understood") or {})
    if spec.topic:
        understood["topic"] = spec.topic
    if spec.artifact_type:
        understood["artifact_type"] = spec.artifact_type
        understood["authoring_mode"] = spec.artifact_type
    if spec.framework:
        understood["framework"] = spec.framework
    if spec.title:
        understood["title"] = spec.title
    if spec.description:
        understood["description"] = spec.description
    if spec.target_population:
        understood["target_population"] = spec.target_population
    draft["understood"] = understood
    draft["candidate_questions"] = [question.model_dump() for question in spec.questions]
    draft["candidate_scoring_rules"] = {"method": spec.scoring_method} if spec.scoring_method else {}
    draft["candidate_risk_bands"] = [band.model_dump() for band in spec.risk_bands]
    draft["candidate_anamnesis_sections"] = [section.model_dump() for section in spec.anamnesis_sections]
    draft["candidate_red_flags"] = list(spec.red_flags)
    draft["candidate_assessment_output"] = spec.assessment_output
    draft["candidate_report_requirements"] = list(spec.report_requirements)
    draft["candidate_diagnostic_inputs"] = list(spec.diagnostic_inputs)
    draft["candidate_rule_nodes"] = [node.model_dump() for node in spec.rule_nodes]
    draft["candidate_conclusion_template"] = spec.conclusion_template
    draft.setdefault("candidate_report_requirements", [])
    draft.setdefault("candidate_safety_requirements", [])
    draft.setdefault("missing_fields", [])
    return draft


def apply_proposal_to_draft(spec: QuestionnaireSpec, operation: EditOperation, base_draft: dict[str, Any] | None = None) -> dict[str, Any]:
    draft = dict(base_draft or default_draft())
    understood = dict(draft.get("understood") or {})

    if spec.topic:
        understood["topic"] = spec.topic
    if spec.artifact_type:
        understood["artifact_type"] = spec.artifact_type
        understood["authoring_mode"] = spec.artifact_type
    if spec.framework:
        understood["framework"] = spec.framework
    if spec.title:
        understood["title"] = spec.title
    if spec.target_population:
        understood["target_population"] = spec.target_population

    target = operation.target_section or ""
    if operation.intent_type in {"replace_description", "regenerate_description"} and spec.description is not None:
        understood["description"] = spec.description
    elif operation.intent_type == "set_framework" and spec.framework:
        understood["framework"] = spec.framework
    elif operation.intent_type in {"replace_questions_from_text", "append_questions_from_text"}:
        current_questions = list(draft.get("candidate_questions") or [])
        new_questions = [question.model_dump() for question in spec.questions]
        draft["candidate_questions"] = current_questions + new_questions if operation.intent_type == "append_questions_from_text" else new_questions
        if spec.scoring_method:
            draft["candidate_scoring_rules"] = {"method": spec.scoring_method}
        if spec.risk_bands:
            draft["candidate_risk_bands"] = [band.model_dump() for band in spec.risk_bands]
    elif operation.intent_type == "replace_risk_bands" or target == "risk_bands":
        draft["candidate_risk_bands"] = [band.model_dump() for band in spec.risk_bands]
        if spec.scoring_method:
            draft["candidate_scoring_rules"] = {"method": spec.scoring_method}
    elif operation.intent_type == "apply_questions_only":
        draft["candidate_questions"] = [question.model_dump() for question in spec.questions]
        if spec.scoring_method:
            draft["candidate_scoring_rules"] = {"method": spec.scoring_method}
    elif operation.intent_type == "apply_risks_only":
        draft["candidate_risk_bands"] = [band.model_dump() for band in spec.risk_bands]
    elif operation.intent_type == "apply_sections_only":
        draft["candidate_anamnesis_sections"] = [section.model_dump() for section in spec.anamnesis_sections]
    elif operation.intent_type == "apply_rules_only":
        draft["candidate_diagnostic_inputs"] = list(spec.diagnostic_inputs)
        draft["candidate_rule_nodes"] = [node.model_dump() for node in spec.rule_nodes]
    elif operation.intent_type == "add_anamnesis_section":
        current_sections = list(draft.get("candidate_anamnesis_sections") or [])
        current_sections.extend(section.model_dump() for section in spec.anamnesis_sections)
        draft["candidate_anamnesis_sections"] = current_sections
    elif operation.intent_type == "replace_rule_nodes":
        draft["candidate_diagnostic_inputs"] = list(spec.diagnostic_inputs)
        draft["candidate_rule_nodes"] = [node.model_dump() for node in spec.rule_nodes]
        draft["candidate_conclusion_template"] = spec.conclusion_template
    else:
        draft = spec_to_draft(spec, draft)
        understood = dict(draft.get("understood") or {})

    if spec.red_flags:
        draft["candidate_red_flags"] = list(spec.red_flags)
    if spec.assessment_output:
        draft["candidate_assessment_output"] = spec.assessment_output
    if spec.report_requirements:
        draft["candidate_report_requirements"] = list(spec.report_requirements)
    if spec.conclusion_template:
        draft["candidate_conclusion_template"] = spec.conclusion_template

    draft["understood"] = understood
    draft.setdefault("candidate_questions", [])
    draft.setdefault("candidate_scoring_rules", {})
    draft.setdefault("candidate_risk_bands", [])
    draft.setdefault("candidate_anamnesis_sections", [])
    draft.setdefault("candidate_red_flags", [])
    draft.setdefault("candidate_assessment_output", None)
    draft.setdefault("candidate_diagnostic_inputs", [])
    draft.setdefault("candidate_rule_nodes", [])
    draft.setdefault("candidate_conclusion_template", None)
    draft.setdefault("candidate_report_requirements", [])
    draft.setdefault("candidate_safety_requirements", [])
    draft.setdefault("missing_fields", [])
    return draft


def review_to_text(review: CriticReview, language: str) -> str:
    if not review.findings and not review.missing_information:
        return "Validation passed." if language != "ru" else "Валидация пройдена."
    lines = ["Validation review:" if language != "ru" else "Результат проверки:"]
    for finding in review.findings:
        lines.append(f"- [{finding.severity}] {finding.message}")
    for item in review.missing_information:
        lines.append(f"- [missing] {item}")
    return "\n".join(lines)


def _spec_has_meaningful_content(spec: QuestionnaireSpec) -> bool:
    return bool(
        spec.topic
        or spec.framework
        or spec.questions
        or spec.description
        or spec.risk_bands
        or spec.scoring_method
        or spec.anamnesis_sections
        or spec.red_flags
        or spec.diagnostic_inputs
        or spec.rule_nodes
        or spec.conclusion_template
        or spec.report_requirements
    )


def _looks_like_section_heading(line: str) -> bool:
    normalized = line.strip().rstrip(":").lower()
    return normalized in {
        "questions",
        "question",
        "вопросы",
        "вопрос",
        "scoring",
        "score",
        "скоринг",
        "подсчет",
        "подсчёт",
        "risk bands",
        "risk band",
        "риск",
        "риски",
        "диапазоны риска",
        "интерпретация суммы баллов",
        "report",
        "reporting",
        "отчет",
        "отчёт",
        "recommendations",
        "рекомендации",
    }


def _extract_structured_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"questions": [], "scoring": [], "risk_bands": [], "report": []}
    current_section = "questions"
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        lowered = stripped.rstrip(":").lower()
        if lowered in {"questions", "question", "вопросы", "вопрос"}:
            current_section = "questions"
            continue
        if lowered in {"scoring", "score", "скоринг", "подсчет", "подсчёт"}:
            current_section = "scoring"
            continue
        if lowered in {"risk bands", "risk band", "риски", "риск", "диапазоны риска", "интерпретация суммы баллов"}:
            current_section = "risk_bands"
            continue
        if lowered in {"report", "reporting", "отчет", "отчёт", "recommendations", "рекомендации"}:
            current_section = "report"
            continue
        sections[current_section].append(raw_line)
    return {key: "\n".join(value).strip() for key, value in sections.items() if "\n".join(value).strip()}


def _parse_report_requirements_block(text: str) -> list[str]:
    requirements: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("-"):
            requirement = line.lstrip("-").strip()
            if requirement:
                requirements.append(requirement)
        elif not _looks_like_section_heading(line):
            requirements.append(line)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in requirements:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _infer_artifact_type(message: str, current: QuestionnaireSpec) -> str:
    inferred = infer_artifact_type(message)
    if inferred != "questionnaire":
        return inferred
    low = message.lower()
    if current.artifact_type == "questionnaire" and any(token in low for token in ["риск", "risk", "score", "скор", "findrisk", "финдриск"]):
        return "questionnaire"
    return current.artifact_type or "questionnaire"


def _normalize_edit_operation(message: str, current: QuestionnaireSpec, operation: EditOperation) -> EditOperation:
    low = message.lower()
    has_numbered_questions = bool(re.search(r"(?m)^\s*\d+[\.)]\s+", message))
    has_scored_options = bool(re.search(r"(?im)^\s*-\s*.+[-—]\s*\d+(?:[.,]\d+)?\s*бал", message))
    has_questionnaire_context = bool(
        current.questions
        or current.risk_bands
        or current.framework
        or current.artifact_type == "questionnaire"
    )
    mentions_questionnaire_scoring = any(
        token in low
        for token in [
            "findrisk",
            "финдриск",
            "опросник",
            "questionnaire",
            "суммируются все баллы",
            "интерпретация суммы баллов",
            "оценка рисков",
            "risk band",
            "risk bands",
            "подсчет баллов",
            "подсчёт баллов",
            "не clinical rule graph",
            "это questionnaire",
        ]
    )
    if operation.intent_type == "replace_risk_bands":
        return operation.model_copy(
            update={
                "target_section": "risk_bands",
                "requires_compilation": True,
                "requires_confirmation": True,
            }
        )
    if operation.intent_type == "replace_rule_nodes" and has_questionnaire_context and mentions_questionnaire_scoring:
        return operation.model_copy(
            update={
                "intent_type": "replace_risk_bands",
                "target_section": "risk_bands",
                "requires_compilation": True,
            }
        )
    if operation.intent_type == "replace_rule_nodes" and has_numbered_questions and has_scored_options and mentions_questionnaire_scoring:
        return operation.model_copy(
            update={
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "framework": operation.framework or ("findrisk" if any(token in low for token in ["findrisk", "финдриск"]) else None),
            }
        )
    if operation.intent_type == "discuss" and has_numbered_questions and has_scored_options and mentions_questionnaire_scoring:
        return operation.model_copy(
            update={
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "framework": operation.framework or ("findrisk" if any(token in low for token in ["findrisk", "финдриск"]) else None),
            }
        )
    if operation.intent_type == "set_framework" and (operation.framework or "").lower() == "findrisk":
        return operation.model_copy(update={"target_section": "framework", "requires_compilation": True})
    return operation


def _normalize_compiled_spec(spec: QuestionnaireSpec, message: str, current: QuestionnaireSpec, operation: EditOperation) -> QuestionnaireSpec:
    low = message.lower()
    explicit_artifact_type = infer_artifact_type(message)
    has_scored_questions = any(question.options and any(option.score is not None for option in question.options) for question in spec.questions)
    findrisk_like = looks_like_findrisk_questionnaire(
        spec.topic or current.topic,
        spec.framework or current.framework or operation.framework,
        [question.model_dump(mode="json") for question in spec.questions],
        message,
    )
    has_questionnaire_signals = any(
        token in low
        for token in [
            "findrisk",
            "финдриск",
            "опросник",
            "questionnaire",
            "суммируются все баллы",
            "интерпретация суммы баллов",
            "балл",
            "score",
            "scoring",
            "risk band",
            "risk bands",
        ]
    )
    should_force_questionnaire = (
        (spec.framework or current.framework or operation.framework or "").lower() == "findrisk"
        or findrisk_like
        or (
            operation.intent_type in {"replace_questions_from_text", "append_questions_from_text", "replace_risk_bands", "set_framework"}
            and has_questionnaire_signals
            and explicit_artifact_type == "questionnaire"
        )
        or (
            spec.artifact_type == "clinical_rule_graph"
            and has_scored_questions
            and operation.intent_type != "replace_rule_nodes"
            and not spec.rule_nodes
            and explicit_artifact_type == "questionnaire"
        )
    )
    if not should_force_questionnaire:
        if (spec.framework or current.framework or operation.framework or "").lower() == "burnout":
            scaffold = draft_to_spec(get_scaffold("stress", "burnout"))
            updates: dict[str, Any] = {}
            if not spec.risk_bands:
                updates["risk_bands"] = scaffold.risk_bands
            if not spec.report_requirements:
                updates["report_requirements"] = scaffold.report_requirements
            if updates:
                return spec.model_copy(update=updates)
        if findrisk_like:
            scaffold = draft_to_spec(get_scaffold("diabetes", "findrisk"))
            updates = {
                "artifact_type": "questionnaire",
                "framework": "findrisk",
                "scoring_method": spec.scoring_method or current.scoring_method or "sum_of_option_scores",
            }
            if not spec.risk_bands:
                updates["risk_bands"] = scaffold.risk_bands
            if not spec.report_requirements:
                updates["report_requirements"] = scaffold.report_requirements
            return spec.model_copy(update=updates)
        return spec
    scoring_method = spec.scoring_method or current.scoring_method or ("sum_of_option_scores" if spec.questions else None)
    updates = {
        "artifact_type": "questionnaire",
        "framework": "findrisk" if findrisk_like else (spec.framework or current.framework or operation.framework),
        "scoring_method": scoring_method,
        "diagnostic_inputs": [],
        "rule_nodes": [],
        "conclusion_template": None,
    }
    if (spec.framework or current.framework or operation.framework or "").lower() == "burnout":
        scaffold = draft_to_spec(get_scaffold("stress", "burnout"))
        if not spec.risk_bands:
            updates["risk_bands"] = scaffold.risk_bands
        if not spec.report_requirements:
            updates["report_requirements"] = scaffold.report_requirements
    if findrisk_like:
        scaffold = draft_to_spec(get_scaffold("diabetes", "findrisk"))
        if not spec.risk_bands:
            updates["risk_bands"] = scaffold.risk_bands
        if not spec.report_requirements:
            updates["report_requirements"] = scaffold.report_requirements
    return spec.model_copy(update=updates)


async def plan_edit_operation(message: str, draft: dict[str, Any], language: str, has_pending_proposal: bool) -> EditOperation:
    current = draft_to_spec(draft)
    payload = {
        "analysis_mode": "specialist_edit_operation",
        "language": language,
        "specialist_message": message,
        "current_draft": draft,
        "pending_proposal_exists": has_pending_proposal,
    }
    raw = await controller_client().complete_json(
        system_prompt=(
            "Return strict JSON for the specialist authoring edit operation. "
            "Allowed intent_type values: discuss, replace_questions_from_text, append_questions_from_text, replace_risk_bands, "
            "add_anamnesis_section, replace_rule_nodes, replace_description, regenerate_description, set_framework, "
            "show_diff, show_versions, rollback_draft, show_preview, show_detailed_draft, show_questions, show_scoring, "
            "show_risks, explain_question_source, compile, publish, apply_pending_proposal, apply_questions_only, "
            "apply_risks_only, apply_sections_only, apply_rules_only, help. "
            "Use requires_confirmation=true for content-changing operations."
        ),
        user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
    )
    try:
        operation = EditOperation.model_validate(raw or {})
    except ValidationError:
        operation = EditOperation(intent_type="discuss", requires_confirmation=True)
    return _normalize_edit_operation(message, current, operation)


def _parse_numbered_questions_block(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    questions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_start_line: int | None = None
    current_condition: str | None = None
    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        if _looks_like_section_heading(line):
            if current:
                if current_start_line is not None:
                    current["source_line_range"] = f"{current_start_line}-{line_no - 1}"
                questions.append(current)
                current = None
                current_start_line = None
                current_condition = None
            continue
        m = re.match(r"^(\d+)[\.)]\s+(.+)$", line)
        if m:
            if current:
                if current_start_line is not None:
                    current["source_line_range"] = f"{current_start_line}-{line_no - 1}"
                questions.append(current)
            current = {
                "id": f"q{m.group(1)}",
                "text": m.group(2).strip(),
                "options": [],
                "notes": [],
                "source_excerpt": raw_line.strip()[:240],
            }
            current_start_line = line_no
            current_condition = None
            continue
        if current is None:
            continue
        if line.endswith(":") and any(token in line.lower() for token in ["для ", "for ", "men", "women", "мужчин", "женщин"]):
            current_condition = line.rstrip(":").strip()
            current["notes"].append(line)
            continue
        if line.startswith("-"):
            option_line = line.lstrip("-").strip()
            next_question_match = re.search(
                r"(?:->|→)\s*(?:go to question|question|go to q|q|к вопросу|вопрос)\s*(\d+)",
                option_line,
                flags=re.IGNORECASE,
            )
            score_match = re.search(r"[-—]\s*(\d+(?:[.,]\d+)?)\s*points?", option_line.lower()) or re.search(
                r"[-—]\s*(\d+(?:[.,]\d+)?)\s*бал",
                option_line.lower(),
            )
            score = float(score_match.group(1).replace(",", ".")) if score_match else 0.0
            label = re.sub(r"\s*(?:->|→)\s*(?:go to question|question|go to q|q|к вопросу|вопрос)\s*\d+\s*$", "", option_line, flags=re.IGNORECASE)
            label = re.sub(r"\s*[-—]\s*\d+(?:[.,]\d+)?\s*points?\.?\s*$", "", label, flags=re.IGNORECASE)
            label = re.sub(r"\s*[-—]\s*\d+(?:[.,]\d+)?\s*бал[а-я]*\.?\s*$", "", label, flags=re.IGNORECASE).strip()
            current["options"].append(
                {
                    "label": label,
                    "value": f"opt_{len(current['options']) + 1}",
                    "score": score,
                    "condition": current_condition,
                    "source_excerpt": raw_line.strip()[:240],
                    "next_question_id": f"q{next_question_match.group(1)}" if next_question_match else None,
                }
            )
            continue
        current["notes"].append(line)
    if current:
        if current_start_line is not None:
            current["source_line_range"] = f"{current_start_line}-{len(lines)}"
        questions.append(current)
    return questions


def _split_band_tail(text: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in re.split(r",\s*", text, maxsplit=1) if part.strip()]
    if not parts:
        return "Risk band", None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


def _parse_risk_bands_block(text: str) -> list[RiskBandSpec]:
    risk_bands: list[RiskBandSpec] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("-"):
            continue
        content = line.lstrip("-").strip()
        content = re.sub(r"\s*->\s*", " — ", content)

        less_than_match = re.match(r"^<\s*(\d+(?:[.,]\d+)?)\s*[—-]\s*(.+)$", content)
        if less_than_match:
            upper = float(less_than_match.group(1).replace(",", "."))
            label, meaning = _split_band_tail(less_than_match.group(2).strip())
            risk_bands.append(RiskBandSpec(min_score=0.0, max_score=upper - 0.0001, label=label, meaning=meaning, source_excerpt=raw_line.strip()[:240]))
            continue

        between_match = re.match(r"^(\d+(?:[.,]\d+)?)\s*[–-]\s*(\d+(?:[.,]\d+)?)\s*[—-]\s*(.+)$", content)
        if between_match:
            start = float(between_match.group(1).replace(",", "."))
            end = float(between_match.group(2).replace(",", "."))
            label, meaning = _split_band_tail(between_match.group(3).strip())
            risk_bands.append(RiskBandSpec(min_score=start, max_score=end, label=label, meaning=meaning, source_excerpt=raw_line.strip()[:240]))
            continue

        plus_match = re.match(r"^(\d+(?:[.,]\d+)?)\+\s*[—-]\s*(.+)$", content)
        if plus_match:
            lower = float(plus_match.group(1).replace(",", "."))
            label, meaning = _split_band_tail(plus_match.group(2).strip())
            risk_bands.append(RiskBandSpec(min_score=lower, max_score=1000.0, label=label, meaning=meaning, source_excerpt=raw_line.strip()[:240]))
            continue

        greater_than_match = re.match(r"^>\s*(\d+(?:[.,]\d+)?)\s*[—-]\s*(.+)$", content)
        if greater_than_match:
            lower = float(greater_than_match.group(1).replace(",", "."))
            label, meaning = _split_band_tail(greater_than_match.group(2).strip())
            risk_bands.append(RiskBandSpec(min_score=lower + 0.0001, max_score=1000.0, label=label, meaning=meaning, source_excerpt=raw_line.strip()[:240]))
    return risk_bands


def _extract_red_flags(text: str) -> list[str]:
    flags: list[str] = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("-*•").strip()
        if not stripped:
            continue
        low = stripped.lower()
        if any(token in low for token in ["red flag", "красн", "urgent", "срочно", "экстр", "alarm symptom"]):
            flags.append(stripped)
    return flags


def _build_anamnesis_sections(parsed_questions: list[dict[str, Any]], message: str) -> list[AnamnesisSectionSpec]:
    if not parsed_questions:
        return []
    title = "Базовый сбор анамнеза" if re.search(r"[а-яА-ЯёЁ]", message) else "Primary anamnesis intake"
    section_questions = []
    for question in parsed_questions:
        section_questions.append(
            {
                "id": question["id"],
                "text": question["text"],
                "question_type": "single_choice" if question["options"] else "text",
                "source": "parsed from specialist message",
                "options": question["options"],
                "notes": "\n".join(question["notes"]).strip() or None,
            }
        )
    return [
        AnamnesisSectionSpec(
            id="section_1",
            title=title,
            goal="Structured anamnesis intake",
            source_excerpt=message[:240],
            questions=section_questions,  # type: ignore[arg-type]
            branching_cues=[],
        )
    ]


def _build_rule_nodes(parsed_questions: list[dict[str, Any]], message: str) -> tuple[list[str], list[ClinicalRuleNodeSpec]]:
    inputs: list[str] = []
    nodes: list[ClinicalRuleNodeSpec] = []
    explicit_nodes = _parse_rule_statements(message)
    if explicit_nodes:
        explicit_inputs = [node.condition or node.label for node in explicit_nodes]
        return explicit_inputs, explicit_nodes
    for idx, question in enumerate(parsed_questions, start=1):
        inputs.append(question["text"])
        outcome = None
        if question["options"]:
            top_option = max(question["options"], key=lambda item: item.get("score", 0.0))
            outcome = f"High concern if `{question['text']}` -> `{top_option.get('label')}`"
        nodes.append(
            ClinicalRuleNodeSpec(
                id=f"rule_{idx}",
                label=question["text"],
                condition=question["text"],
                conditions_ast=[],
                outcome=outcome,
                next_node_id=f"rule_{idx + 1}" if idx < len(parsed_questions) else None,
                source="parsed from specialist message",
                source_excerpt=question.get("source_excerpt"),
            )
        )
    if not nodes and message.strip():
        first_line = next((line.strip() for line in message.splitlines() if line.strip()), "clinical rule")
        nodes.append(
            ClinicalRuleNodeSpec(
                id="rule_1",
                label=first_line[:120],
                condition=first_line[:240],
                conditions_ast=[],
                outcome="Needs specialist refinement",
                source="parsed from specialist message",
                source_excerpt=first_line[:240],
            )
        )
        inputs.append(first_line[:120])
    return inputs, nodes


def _parse_anamnesis_sections(text: str) -> list[AnamnesisSectionSpec]:
    parsed_questions = _parse_numbered_questions_block(text)
    return _build_anamnesis_sections(parsed_questions, text)


def _parse_rule_statements(text: str) -> list[ClinicalRuleNodeSpec]:
    nodes: list[ClinicalRuleNodeSpec] = []
    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip().lstrip("-").strip()
        if not line:
            continue
        match = re.match(r"^(?:если|if)\s+(.+?)(?:,\s*то|\s+then)\s+(.+)$", line, flags=re.IGNORECASE)
        if not match:
            continue
        condition = match.group(1).strip()
        outcome = match.group(2).strip()
        ast = _parse_condition_expression(condition)
        nodes.append(
            ClinicalRuleNodeSpec(
                id=f"rule_explicit_{len(nodes) + 1}",
                label=condition[:120],
                condition=condition,
                conditions_ast=ast,
                outcome=outcome,
                next_node_id=None,
                source="parsed explicit rule",
                source_excerpt=raw_line.strip()[:240],
            )
        )
    for idx, node in enumerate(nodes[:-1]):
        node.next_node_id = nodes[idx + 1].id
    return nodes


def _parse_condition_expression(condition: str) -> list[dict[str, str]]:
    ast: list[dict[str, str]] = []
    patterns = [
        r"(?P<field>.+?)\s*(?P<op>>=|<=|>|<|=)\s*(?P<value>-?\d+(?:[.,]\d+)?)",
        r"(?P<field>.+?)\s*(?P<op>contains)\s*(?P<value>.+)",
    ]
    for pattern in patterns:
        match = re.match(pattern, condition.strip(), flags=re.IGNORECASE)
        if not match:
            continue
        ast.append(
            {
                "field": match.group("field").strip(),
                "operator": match.group("op").strip(),
                "value": match.group("value").strip(),
            }
        )
        break
    if not ast and condition.strip():
        ast.append({"field": condition.strip(), "operator": "present", "value": ""})
    return ast


def _heuristic_compile_spec(message: str, draft: dict[str, Any], operation: EditOperation) -> QuestionnaireSpec:
    current = draft_to_spec(draft)
    artifact_type = _infer_artifact_type(message, current)
    topic = infer_scaffold_topic(message) or current.topic
    framework = operation.framework or infer_scaffold_framework(message) or current.framework
    scaffold = get_scaffold(topic, framework)
    scaffold_spec = draft_to_spec(scaffold) if scaffold else QuestionnaireSpec(topic=topic, framework=framework)

    if operation.intent_type == "regenerate_description":
        description = (
            f"Assessment for early screening of {framework.upper() if framework else topic}."
            if topic
            else "Assessment draft."
        )
        current.description = description
        return current

    sections = _extract_structured_sections(message)
    question_text = sections.get("questions") or message
    risk_text = sections.get("risk_bands") or message
    report_text = sections.get("report") or ""
    parsed_questions = _parse_numbered_questions_block(question_text)
    parsed_risk_bands = _parse_risk_bands_block(risk_text)
    report_requirements = _parse_report_requirements_block(report_text)
    anamnesis_sections = _build_anamnesis_sections(parsed_questions, message) if artifact_type == "anamnesis_flow" else current.anamnesis_sections
    diagnostic_inputs, rule_nodes = _build_rule_nodes(parsed_questions, message) if artifact_type == "clinical_rule_graph" else (current.diagnostic_inputs, current.rule_nodes)
    red_flags = current.red_flags or _extract_red_flags(message)
    if operation.intent_type == "add_anamnesis_section":
        return QuestionnaireSpec(
            artifact_type="anamnesis_flow",
            topic=topic or current.topic or scaffold_spec.topic,
            framework=framework or current.framework or scaffold_spec.framework,
            title=current.title or scaffold_spec.title,
            description=current.description or scaffold_spec.description,
            target_population=current.target_population or scaffold_spec.target_population,
            questions=current.questions,
            scoring_method=current.scoring_method,
            risk_bands=current.risk_bands,
            anamnesis_sections=_parse_anamnesis_sections(message),
            red_flags=red_flags,
            assessment_output=current.assessment_output,
            report_requirements=report_requirements or current.report_requirements,
            diagnostic_inputs=current.diagnostic_inputs,
            rule_nodes=current.rule_nodes,
            conclusion_template=current.conclusion_template,
            source_excerpt=message[:1000],
        )
    if operation.intent_type == "replace_rule_nodes":
        rule_inputs, compiled_rule_nodes = _build_rule_nodes(parsed_questions, message)
        return QuestionnaireSpec(
            artifact_type="clinical_rule_graph",
            topic=topic or current.topic or scaffold_spec.topic,
            framework=framework or current.framework or scaffold_spec.framework,
            title=current.title or scaffold_spec.title,
            description=current.description or scaffold_spec.description,
            target_population=current.target_population or scaffold_spec.target_population,
            questions=current.questions,
            scoring_method=None,
            risk_bands=[],
            anamnesis_sections=current.anamnesis_sections,
            red_flags=red_flags,
            assessment_output=current.assessment_output,
            report_requirements=report_requirements or current.report_requirements,
            diagnostic_inputs=rule_inputs,
            rule_nodes=compiled_rule_nodes,
            conclusion_template=current.conclusion_template or "Clinical rule interpretation requires specialist confirmation.",
            source_excerpt=message[:1000],
        )
    if parsed_risk_bands and not parsed_questions:
        return QuestionnaireSpec(
            artifact_type=artifact_type,
            topic=topic or current.topic or scaffold_spec.topic,
            framework=framework or current.framework or scaffold_spec.framework,
            title=current.title or scaffold_spec.title,
            description=current.description or scaffold_spec.description,
            target_population=current.target_population or scaffold_spec.target_population,
            questions=current.questions or scaffold_spec.questions,
            scoring_method=current.scoring_method or scaffold_spec.scoring_method or "sum_of_option_scores",
            risk_bands=parsed_risk_bands,
            anamnesis_sections=current.anamnesis_sections,
            red_flags=red_flags,
            assessment_output=current.assessment_output,
            report_requirements=report_requirements or current.report_requirements,
            diagnostic_inputs=current.diagnostic_inputs,
            rule_nodes=current.rule_nodes,
            conclusion_template=current.conclusion_template,
            source_excerpt=message[:1000],
        )
    if parsed_questions:
        spec_questions = []
        for question in parsed_questions:
            options = [QuestionOptionSpec(**option) for option in question["options"]]
            notes = "\n".join(question["notes"]).strip() or None
            spec_questions.append(
                {
                    "id": question["id"],
                    "text": question["text"],
                    "question_type": "single_choice",
                    "source": "parsed from specialist message",
                    "source_excerpt": question.get("source_excerpt"),
                    "source_line_range": question.get("source_line_range"),
                    "options": [option.model_dump() for option in options],
                    "notes": notes,
                }
            )
        scoring_method = "sum_of_option_scores"
        if looks_like_findrisk_questionnaire(topic, framework, spec_questions, message):
            framework = "findrisk"
            scaffold = get_scaffold("diabetes", "findrisk")
            scaffold_spec = draft_to_spec(scaffold)
        risk_bands = current.risk_bands or scaffold_spec.risk_bands
        return QuestionnaireSpec(
            artifact_type=artifact_type,
            topic=topic or current.topic or scaffold_spec.topic,
            framework=framework or current.framework or scaffold_spec.framework,
            title=current.title or scaffold_spec.title,
            description=current.description,
            target_population=current.target_population,
            questions=spec_questions,  # type: ignore[arg-type]
            scoring_method=scoring_method if artifact_type == "questionnaire" else None,
            risk_bands=risk_bands if artifact_type == "questionnaire" else [],
            anamnesis_sections=anamnesis_sections,
            red_flags=red_flags,
            assessment_output=current.assessment_output,
            report_requirements=report_requirements or current.report_requirements,
            diagnostic_inputs=diagnostic_inputs,
            rule_nodes=rule_nodes,
            conclusion_template=current.conclusion_template,
            source_excerpt=message[:1000],
        )

    return QuestionnaireSpec(
        artifact_type=artifact_type,
        topic=topic or current.topic or scaffold_spec.topic,
        framework=framework or current.framework or scaffold_spec.framework,
        title=current.title or scaffold_spec.title,
        description=current.description or scaffold_spec.description,
        target_population=current.target_population or scaffold_spec.target_population,
        questions=current.questions or scaffold_spec.questions,
        scoring_method=(current.scoring_method or scaffold_spec.scoring_method) if artifact_type == "questionnaire" else None,
        risk_bands=(current.risk_bands or scaffold_spec.risk_bands) if artifact_type == "questionnaire" else [],
        anamnesis_sections=current.anamnesis_sections or anamnesis_sections,
        red_flags=current.red_flags or red_flags,
        assessment_output=current.assessment_output,
        report_requirements=current.report_requirements or report_requirements,
        diagnostic_inputs=current.diagnostic_inputs or diagnostic_inputs,
        rule_nodes=current.rule_nodes or rule_nodes,
        conclusion_template=current.conclusion_template,
        source_excerpt=message[:1000],
    )


async def compile_questionnaire_spec(message: str, draft: dict[str, Any], operation: EditOperation, language: str) -> QuestionnaireSpec:
    current = draft_to_spec(draft)
    payload = {
        "language": language,
        "specialist_message": message,
        "current_spec": current.model_dump(mode="json"),
        "operation": operation.model_dump(mode="json"),
    }
    raw = await specialist_compiler_client().complete_json(
        system_prompt=(
            "Compile specialist source text into a clinical authoring spec. Return strict JSON with keys: "
            "artifact_type, topic, framework, title, description, target_population, questions, scoring_method, risk_bands, "
            "anamnesis_sections, red_flags, assessment_output, report_requirements, diagnostic_inputs, rule_nodes, conclusion_template, source_excerpt. "
            "Each question must preserve real answer options and numeric scores. Do not collapse multi-option questions into yes/no."
        ),
        user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
    )
    try:
        spec = QuestionnaireSpec.model_validate(raw or {})
    except ValidationError:
        spec = _heuristic_compile_spec(message, draft, operation)
    if not _spec_has_meaningful_content(spec):
        spec = _heuristic_compile_spec(message, draft, operation)

    heuristic = _heuristic_compile_spec(message, draft, operation)
    # Fallback upgrade when model returned underspecified or structurally poorer output.
    if spec.questions and all(len(question.options) <= 2 for question in spec.questions):
        if any(len(question.options) > 2 for question in heuristic.questions):
            spec = heuristic
    if not spec.risk_bands and heuristic.risk_bands:
        spec = spec.model_copy(update={"risk_bands": heuristic.risk_bands})
    if spec.questions and heuristic.questions:
        spec_question_map = {question.id: question for question in spec.questions}
        merged_questions = []
        improved = False
        for heuristic_question in heuristic.questions:
            current_question = spec_question_map.get(heuristic_question.id)
            if current_question is None:
                merged_questions.append(heuristic_question)
                improved = True
                continue
            current_has_branching = any(option.next_question_id for option in current_question.options)
            heuristic_has_branching = any(option.next_question_id for option in heuristic_question.options)
            if heuristic_has_branching and not current_has_branching:
                merged_questions.append(heuristic_question)
                improved = True
            else:
                merged_questions.append(current_question)
        if improved:
            spec = spec.model_copy(update={"questions": merged_questions})
    return _normalize_compiled_spec(spec, message, current, operation)


def local_validate_spec(spec: QuestionnaireSpec, operation: EditOperation) -> CriticReview:
    findings: list[ValidationFinding] = []
    missing_information: list[str] = []

    if spec.artifact_type == "questionnaire" and operation.intent_type in {"replace_questions_from_text", "append_questions_from_text"} and not spec.questions:
        findings.append(ValidationFinding(severity="error", message="No questions were extracted from the specialist source text.", field_path="questions"))
    if spec.artifact_type == "questionnaire" and operation.intent_type == "replace_risk_bands" and not spec.risk_bands:
        findings.append(ValidationFinding(severity="error", message="No risk bands were extracted from the specialist source text.", field_path="risk_bands"))

    if spec.artifact_type == "questionnaire" and spec.questions:
        for idx, question in enumerate(spec.questions, start=1):
            if question.question_type == "single_choice" and len(question.options) < 2:
                findings.append(
                    ValidationFinding(
                        severity="error",
                        message=f"Question {idx} has too few options for single_choice.",
                        field_path=f"questions[{idx - 1}].options",
                    )
                )
    if spec.framework and spec.framework.lower() == "findrisk" and len(spec.questions) < 8:
        missing_information.append("FINDRISC-like questionnaire is expected to include 8 canonical questions or an explicit adapted variant.")

    if spec.artifact_type == "anamnesis_flow":
        if not spec.anamnesis_sections:
            findings.append(ValidationFinding(severity="error", message="Anamnesis flow requires at least one section.", field_path="anamnesis_sections"))
        if not any(section.questions for section in spec.anamnesis_sections):
            missing_information.append("Anamnesis sections do not contain concrete questions yet.")

    if spec.artifact_type == "clinical_rule_graph":
        if not spec.diagnostic_inputs:
            findings.append(ValidationFinding(severity="error", message="Clinical rule graph requires diagnostic inputs.", field_path="diagnostic_inputs"))
        if not spec.rule_nodes:
            findings.append(ValidationFinding(severity="error", message="Clinical rule graph requires at least one rule node.", field_path="rule_nodes"))

    if spec.description and any(token in spec.description.lower() for token in ["удали", "исправ", "попробуй", "generate", "сгенерируй", "deski", "дескипшен"]):
        findings.append(ValidationFinding(severity="error", message="Description contains editor instructions instead of clinical narrative.", field_path="description"))

    unsafe_texts = [spec.description or "", spec.conclusion_template or ""]
    for text in unsafe_texts:
        low = text.lower()
        if any(token in low for token in ["назнач", "prescribe", "start metformin", "терап", "лечен", "take insulin", "диагноз подтвержден"]):
            findings.append(ValidationFinding(severity="error", message="Spec contains unsafe diagnosis or treatment language.", field_path="clinical_safety"))

    if spec.artifact_type == "questionnaire" and spec.scoring_method and spec.scoring_method == "sum_of_option_scores" and not spec.risk_bands:
        missing_information.append("Risk bands are missing for sum_of_option_scores.")

    if spec.artifact_type == "questionnaire" and spec.questions:
        missing_sources = [question.id for question in spec.questions if not question.source]
        if missing_sources:
            missing_information.append("Some questions are missing source traceability.")

    has_error = any(finding.severity == "error" for finding in findings)
    severity = "error" if has_error else ("warning" if findings or missing_information else "info")
    return CriticReview(
        is_valid=not has_error,
        severity=severity,  # type: ignore[arg-type]
        findings=findings,
        missing_information=missing_information,
        proposed_repairs=[],
        should_block_apply=has_error,
    )


async def critic_review_spec(message: str, spec: QuestionnaireSpec, operation: EditOperation, language: str) -> CriticReview:
    local_review = local_validate_spec(spec, operation)
    payload = {
        "language": language,
        "specialist_message": message,
        "operation": operation.model_dump(mode="json"),
        "questionnaire_spec": spec.model_dump(mode="json"),
    }
    raw = await specialist_critic_client().complete_json(
        system_prompt=(
            "Review the compiled clinical authoring spec against the specialist source text. Return strict JSON with keys: "
            "is_valid, severity, findings, missing_information, proposed_repairs, should_block_apply. "
            "Block apply when score mappings, framework logic, option structures, anamnesis structure, or diagnostic rule logic are lost or distorted."
        ),
        user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
    )
    try:
        model_review = CriticReview.model_validate(raw or {})
    except ValidationError:
        model_review = CriticReview()

    findings = [*local_review.findings, *model_review.findings]
    missing_information = list(dict.fromkeys([*local_review.missing_information, *model_review.missing_information]))
    proposed_repairs = list(dict.fromkeys([*local_review.proposed_repairs, *model_review.proposed_repairs]))
    should_block = local_review.should_block_apply or model_review.should_block_apply
    severity = "error" if should_block else ("warning" if findings or missing_information else "info")
    return CriticReview(
        is_valid=not should_block,
        severity=severity,  # type: ignore[arg-type]
        findings=findings,
        missing_information=missing_information,
        proposed_repairs=proposed_repairs,
        should_block_apply=should_block,
    )


def proposal_summary(proposal: PendingProposal, language: str) -> str:
    spec = proposal.spec
    review = proposal.review
    current_spec = None
    lines = [
        "Я подготовил предложение, но еще не применял его к draft." if language == "ru" else "I prepared a proposal, but I have not applied it to the draft yet.",
        "",
        "Предложение draft:" if language == "ru" else "Draft proposal:",
        f"- Artifact type: {spec.artifact_type}",
        f"- Topic: {spec.topic or '—'}",
        f"- Framework: {spec.framework or '—'}",
        f"- Questions: {len(spec.questions)}",
        f"- Anamnesis sections: {len(spec.anamnesis_sections)}",
        f"- Rule nodes: {len(spec.rule_nodes)}",
        f"- Scoring: {spec.scoring_method or '—'}",
        f"- Risk bands: {len(spec.risk_bands)}",
    ]
    if review.findings or review.missing_information:
        lines.append("")
        lines.append(review_to_text(review, language))
    return "\n".join(lines)


def diff_summary(current_spec: QuestionnaireSpec, proposed_spec: QuestionnaireSpec, language: str) -> str:
    changes: list[str] = []
    if current_spec.artifact_type != proposed_spec.artifact_type:
        changes.append(f"artifact_type: {current_spec.artifact_type} -> {proposed_spec.artifact_type}")
    if current_spec.topic != proposed_spec.topic:
        changes.append(f"topic: {current_spec.topic or '—'} -> {proposed_spec.topic or '—'}")
    if current_spec.framework != proposed_spec.framework:
        changes.append(f"framework: {current_spec.framework or '—'} -> {proposed_spec.framework or '—'}")
    if current_spec.description != proposed_spec.description:
        changes.append("description: updated")
    if len(current_spec.questions) != len(proposed_spec.questions):
        changes.append(f"questions: {len(current_spec.questions)} -> {len(proposed_spec.questions)}")
    if len(current_spec.anamnesis_sections) != len(proposed_spec.anamnesis_sections):
        changes.append(f"anamnesis_sections: {len(current_spec.anamnesis_sections)} -> {len(proposed_spec.anamnesis_sections)}")
    if len(current_spec.rule_nodes) != len(proposed_spec.rule_nodes):
        changes.append(f"rule_nodes: {len(current_spec.rule_nodes)} -> {len(proposed_spec.rule_nodes)}")
    if current_spec.scoring_method != proposed_spec.scoring_method:
        changes.append(f"scoring: {current_spec.scoring_method or '—'} -> {proposed_spec.scoring_method or '—'}")
    if len(current_spec.risk_bands) != len(proposed_spec.risk_bands):
        changes.append(f"risk_bands: {len(current_spec.risk_bands)} -> {len(proposed_spec.risk_bands)}")
    if not changes:
        return "No structural changes." if language != "ru" else "Структурных изменений нет."
    prefix = "Planned changes:" if language != "ru" else "Планируемые изменения:"
    return prefix + "\n" + "\n".join(f"- {item}" for item in changes)


def detailed_diff_summary(current_spec: QuestionnaireSpec, proposed_spec: QuestionnaireSpec, language: str) -> str:
    lines = [diff_summary(current_spec, proposed_spec, language)]
    if current_spec.questions != proposed_spec.questions:
        current_titles = [question.text for question in current_spec.questions]
        proposed_titles = [question.text for question in proposed_spec.questions]
        added = [title for title in proposed_titles if title not in current_titles]
        removed = [title for title in current_titles if title not in proposed_titles]
        if added:
            lines.append(("Added questions:" if language != "ru" else "Добавленные вопросы:") + "\n" + "\n".join(f"- {item}" for item in added))
        if removed:
            lines.append(("Removed questions:" if language != "ru" else "Удаленные вопросы:") + "\n" + "\n".join(f"- {item}" for item in removed))
    if current_spec.risk_bands != proposed_spec.risk_bands and proposed_spec.risk_bands:
        lines.append("Risk bands:\n" + "\n".join(f"- {band.label}: {band.min_score}..{band.max_score}" for band in proposed_spec.risk_bands))
    if current_spec.anamnesis_sections != proposed_spec.anamnesis_sections and proposed_spec.anamnesis_sections:
        lines.append(("Anamnesis sections:" if language != "ru" else "Секции анамнеза:") + "\n" + "\n".join(f"- {section.title}" for section in proposed_spec.anamnesis_sections))
    if current_spec.rule_nodes != proposed_spec.rule_nodes and proposed_spec.rule_nodes:
        lines.append(("Rule nodes:" if language != "ru" else "Правила:") + "\n" + "\n".join(f"- {node.label}" for node in proposed_spec.rule_nodes))
    return "\n\n".join(lines)
