from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from hea.shared.scaffold_registry import get_scaffold, looks_like_findrisk_questionnaire


def merge_dicts(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            if value:
                merged[key] = merge_dicts(dict(merged[key]), value)
        elif isinstance(value, dict):
            if value or key not in merged:
                merged[key] = value
        elif isinstance(value, list):
            if value or key not in merged:
                merged[key] = value
        elif value is None:
            continue
        elif value == "" and merged.get(key):
            continue
        else:
            merged[key] = value
    return merged


def default_draft() -> dict[str, Any]:
    return {
        "understood": {"authoring_mode": "questionnaire"},
        "candidate_questions": [],
        "candidate_scoring_rules": {},
        "candidate_risk_bands": [],
        "candidate_anamnesis_sections": [],
        "candidate_red_flags": [],
        "candidate_assessment_output": None,
        "candidate_diagnostic_inputs": [],
        "candidate_rule_nodes": [],
        "candidate_conclusion_template": None,
        "candidate_report_requirements": [],
        "candidate_safety_requirements": [],
        "missing_fields": [],
    }


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "assessment"


def compile_graph_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    understood = draft.get("understood", {}) or {}
    artifact_type = understood.get("artifact_type") or "questionnaire"
    topic = understood.get("topic") or "assessment"
    framework = understood.get("framework")
    questions = draft.get("candidate_questions", []) or []
    scoring = draft.get("candidate_scoring_rules", {}) or {}
    risk_bands = draft.get("candidate_risk_bands", []) or []
    anamnesis_sections = draft.get("candidate_anamnesis_sections", []) or []
    red_flags = draft.get("candidate_red_flags", []) or []
    assessment_output = draft.get("candidate_assessment_output")
    report_requirements = draft.get("candidate_report_requirements", []) or []
    diagnostic_inputs = draft.get("candidate_diagnostic_inputs", []) or []
    rule_nodes = draft.get("candidate_rule_nodes", []) or []
    conclusion_template = draft.get("candidate_conclusion_template")

    if artifact_type == "questionnaire" and questions and looks_like_findrisk_questionnaire(topic, framework, questions):
        framework = "findrisk"
        understood["framework"] = framework

    if artifact_type == "questionnaire" and questions and framework in {"burnout", "findrisk"}:
        scaffold = get_scaffold(topic, framework)
        if not risk_bands:
            risk_bands = list(scaffold.get("candidate_risk_bands") or [])
        if not report_requirements:
            report_requirements = list(scaffold.get("candidate_report_requirements") or [])

    feedback: list[str] = []
    if not understood.get("topic"):
        feedback.append("Topic is missing")
    if artifact_type == "questionnaire":
        if not questions:
            feedback.append("At least one question is required")
        if not scoring.get("method"):
            feedback.append("Scoring logic is missing")
        if not risk_bands:
            feedback.append("Risk bands are missing")
    elif artifact_type == "anamnesis_flow":
        if not anamnesis_sections:
            feedback.append("At least one anamnesis section is required")
    elif artifact_type == "clinical_rule_graph":
        if not diagnostic_inputs:
            feedback.append("Diagnostic inputs are missing")
        if not rule_nodes:
            feedback.append("At least one clinical rule node is required")

    if feedback:
        return {
            "status": "invalid",
            "graph_id": None,
            "graph": None,
            "feedback": feedback,
        }

    seed = str(topic) + "|" + "|".join(str(q.get("text", "")) for q in questions if isinstance(q, dict))
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    graph_id = f"{slugify(str(topic))}_{digest}"

    graph = {
        "graph_id": graph_id,
        "title": str(topic).replace("_", " ").title(),
        "artifact_type": artifact_type,
        "topic": topic,
        "description": understood.get("description") or f"Assessment for {topic}",
        "tags": understood.get("tags") or [slugify(str(topic))],
        "entry_signals": understood.get("entry_signals") or [str(topic)],
        "questions": questions,
        "risk_bands": risk_bands,
        "scoring": scoring,
        "anamnesis_sections": anamnesis_sections,
        "red_flags": red_flags,
        "assessment_output": assessment_output,
        "diagnostic_inputs": diagnostic_inputs,
        "rule_nodes": rule_nodes,
        "rule_ast": [node.get("conditions_ast", []) for node in rule_nodes if isinstance(node, dict)],
        "conclusion_template": conclusion_template,
        "report_rules": report_requirements,
        "safety_rules": draft.get("candidate_safety_requirements", []) or [],
        "source_draft": draft,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    if artifact_type == "clinical_rule_graph" and not graph["questions"]:
        graph["questions"] = [
            {
                "id": f"input_{idx + 1}",
                "text": str(item),
                "question_type": "number",
                "options": [],
                "source": "compiled from diagnostic_inputs",
            }
            for idx, item in enumerate(diagnostic_inputs)
        ]

    return {
        "status": "compiled",
        "graph_id": graph_id,
        "graph": graph,
        "feedback": [],
    }
