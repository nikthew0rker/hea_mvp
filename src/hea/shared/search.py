from __future__ import annotations

import re
from typing import Any

from hea.shared.registry import list_graphs


CONCEPT_SYNONYMS = {
    "diabetes": {
        "diabetes",
        "diabet",
        "diabetic",
        "glucose",
        "blood glucose",
        "blood sugar",
        "sugar",
        "glycemia",
        "hyperglycemia",
        "диабет",
        "глюкоза",
        "сахар",
        "сахар в крови",
    },
    "sleep": {
        "sleep",
        "sleeping",
        "insomnia",
        "сон",
        "бессонница",
    },
    "stress": {
        "stress",
        "burnout",
        "anxiety",
        "стресс",
        "выгорание",
        "тревога",
    },
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_]+", text.lower())
        if len(token) >= 3
    }


def _string_list(items: list[Any] | None) -> list[str]:
    return [str(item) for item in (items or []) if str(item).strip()]


def _concept_tokens(text: str) -> set[str]:
    low = text.lower()
    concepts = set()
    for concept, synonyms in CONCEPT_SYNONYMS.items():
        if any(synonym in low for synonym in synonyms):
            concepts.add(concept)
    return concepts


def search_graphs(query: str, top_k: int = 5, extra_context: str = "", intake: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    full_query = " ".join(part for part in [query, extra_context] if part).strip()
    query_tokens = _tokens(full_query)
    query_concepts = _concept_tokens(full_query)
    qlow = full_query.lower()
    intake = intake or {}
    intake_topics = _string_list(intake.get("suspected_topics"))
    intake_symptoms = _string_list(intake.get("symptoms"))
    intake_severity = str(intake.get("severity") or "")

    results: list[dict[str, Any]] = []
    for graph in list_graphs():
        title = str(graph.get("title", ""))
        topic = str(graph.get("topic", ""))
        description = str(graph.get("description", ""))
        artifact_type = str(graph.get("artifact_type", "questionnaire"))
        tags = [str(x) for x in graph.get("tags", [])]
        entry_signals = [str(x) for x in graph.get("entry_signals", [])]

        meta_text = " ".join([title, topic, description, artifact_type] + tags + entry_signals)
        meta_tokens = _tokens(meta_text)
        meta_concepts = _concept_tokens(meta_text)

        score = 0.0
        reasons: list[str] = []

        overlap = query_tokens & meta_tokens
        if overlap:
            score += float(len(overlap)) * 2.0
            reasons.append(f"overlap={', '.join(sorted(list(overlap))[:4])}")

        concept_overlap = query_concepts & meta_concepts
        if concept_overlap:
            score += float(len(concept_overlap)) * 4.0
            reasons.append(f"concept={', '.join(sorted(concept_overlap))}")

        for tag in tags:
            if tag.lower() in qlow:
                score += 3.0
                reasons.append(f"tag={tag}")

        for signal in entry_signals:
            if signal.lower() in qlow:
                score += 4.0
                reasons.append(f"signal={signal}")

        if title and title.lower() in qlow:
            score += 4.0
            reasons.append("title")
        if topic and topic.lower() in qlow:
            score += 3.0
            reasons.append("topic")
        if artifact_type and artifact_type.lower() in qlow:
            score += 2.0
            reasons.append(f"artifact={artifact_type}")

        for intake_topic in intake_topics:
            low_topic = intake_topic.lower()
            if low_topic == topic.lower() or low_topic in {tag.lower() for tag in tags} or low_topic in meta_concepts:
                score += 5.0
                reasons.append(f"intake_topic={intake_topic}")

        for symptom in intake_symptoms:
            low_symptom = symptom.lower()
            symptom_concepts = _concept_tokens(low_symptom)
            if low_symptom in meta_tokens or any(low_symptom in signal.lower() for signal in entry_signals) or bool(symptom_concepts & meta_concepts):
                score += 2.5
                reasons.append(f"symptom={symptom}")

        if intake_severity in {"moderate", "severe"} and artifact_type == "clinical_rule_graph":
            score += 1.5
            reasons.append(f"severity={intake_severity}")

        if score > 0:
            results.append(
                {
                    "graph_id": graph["graph_id"],
                    "score": score,
                    "reason": "; ".join(dict.fromkeys(reasons))[:240],
                    "metadata": {
                        "title": graph.get("title"),
                        "topic": graph.get("topic"),
                        "description": graph.get("description"),
                        "artifact_type": artifact_type,
                        "questions_count": len(graph.get("questions", [])),
                        "estimated_time_minutes": max(1, (len(graph.get("questions", [])) + 2) // 3),
                    },
                    "graph": graph,
                }
            )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]
