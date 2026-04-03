from __future__ import annotations

import re
from typing import Any


def normalize_noisy_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def infer_topic(text: str) -> str | None:
    low = text.lower()
    if any(token in low for token in ["diabet", "диабет", "glucose", "глюкоз", "сахарн", "сахар", "blood sugar", "blood glucose", "glycem"]):
        return "diabetes"
    if any(token in low for token in ["sleep", "сон", "insomnia", "бессон"]):
        return "sleep"
    if any(token in low for token in ["stress", "стресс", "burnout", "выгоран"]):
        return "stress"
    return None


def infer_artifact_type(text: str) -> str:
    low = text.lower()
    if any(token in low for token in ["анамнез", "anamnesis", "history taking", "chief complaint", "жалоб"]):
        return "anamnesis_flow"
    if any(token in low for token in ["clinical rule", "rule graph", "decision tree", "triage", "диагностическ", "decision support", "алгоритм диагности", "схема диагности", "клиническая схема"]):
        return "clinical_rule_graph"
    return "questionnaire"


def _extract_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for line in normalize_noisy_text(text).splitlines():
        stripped = line.strip(" -*•\t")
        if not stripped:
            continue
        if line.strip().startswith(("-", "*", "•")):
            bullets.append(stripped)
    return bullets


def extract_questions(text: str) -> list[dict[str, Any]]:
    bullets = _extract_bullets(text)
    questions: list[dict[str, Any]] = []

    for idx, bullet in enumerate(bullets, start=1):
        if bullet.endswith("?") or any(token in bullet.lower() for token in ["question", "вопрос", "ask", "symptom", "симптом"]):
            questions.append(
                {
                    "id": f"q{idx}",
                    "text": bullet,
                    "question_type": "single_choice",
                    "source": "parsed from specialist message",
                    "options": [
                        {"label": "No", "value": "no", "score": 0},
                        {"label": "Yes", "value": "yes", "score": 1},
                    ],
                }
            )

    # numbered questions
    for match in re.finditer(r"(?m)^\s*(\d+)[\.)]\s+(.+)$", normalize_noisy_text(text)):
        q_text = match.group(2).strip()
        if len(q_text) >= 4:
            questions.append(
                {
                    "id": f"q{len(questions) + 1}",
                    "text": q_text,
                    "question_type": "single_choice",
                    "source": "parsed from specialist message",
                    "options": [
                        {"label": "No", "value": "no", "score": 0},
                        {"label": "Yes", "value": "yes", "score": 1},
                    ],
                }
            )

    # Deduplicate by text
    seen = set()
    unique: list[dict[str, Any]] = []
    for question in questions:
        text_key = question["text"].strip().lower()
        if text_key not in seen:
            seen.add(text_key)
            unique.append(question)
    return unique


def extract_scoring_rules(text: str) -> dict[str, Any]:
    low = text.lower()
    if any(token in low for token in ["score", "балл", "sum", "сумм", "points"]):
        return {"method": "sum_of_option_scores"}
    return {}


def extract_risk_bands(text: str) -> list[dict[str, Any]]:
    normalized = normalize_noisy_text(text)
    risk_bands: list[dict[str, Any]] = []

    # explicit score ranges
    pattern = re.compile(
        r"(?i)(low|elevated|high|низк\w* риск|повышенн\w* риск|высок\w* риск)\s*[:\-]?\s*(\d+)\s*[-–]\s*(\d+)"
    )
    for label, start, end in pattern.findall(normalized):
        risk_bands.append(
            {
                "min_score": int(start),
                "max_score": int(end),
                "label": label,
                "meaning": f"Detected from noisy text: {label}",
            }
        )

    if risk_bands:
        return risk_bands

    topic = infer_topic(text)
    if topic == "diabetes":
        return [
            {"min_score": 0, "max_score": 6, "label": "Low risk", "meaning": "Low estimated risk in this screening graph."},
            {"min_score": 7, "max_score": 11, "label": "Elevated risk", "meaning": "Elevated estimated risk in this screening graph."},
            {"min_score": 12, "max_score": 1000, "label": "High risk", "meaning": "High estimated risk in this screening graph."},
        ]
    if topic == "sleep":
        return [
            {"min_score": 0, "max_score": 2, "label": "Low risk", "meaning": "Low estimated sleep-related risk in this screening graph."},
            {"min_score": 3, "max_score": 1000, "label": "Elevated risk", "meaning": "Elevated sleep-related risk in this screening graph."},
        ]
    return []


def extract_candidate_update(text: str, current_draft: dict[str, Any] | None = None) -> dict[str, Any]:
    current_draft = current_draft or {}
    text = normalize_noisy_text(text)
    topic = infer_topic(text) or (current_draft.get("understood", {}) or {}).get("topic")
    artifact_type = infer_artifact_type(text) or (current_draft.get("understood", {}) or {}).get("artifact_type") or "questionnaire"
    questions = extract_questions(text)
    scoring = extract_scoring_rules(text)
    risk_bands = extract_risk_bands(text)

    update: dict[str, Any] = {
        "understood": {},
        "candidate_questions": questions,
        "candidate_scoring_rules": scoring,
        "candidate_risk_bands": risk_bands,
        "candidate_report_requirements": [],
        "candidate_safety_requirements": [],
        "missing_fields": [],
    }
    if topic:
        update["understood"]["topic"] = topic
        update["understood"]["description"] = text[:300]
        update["understood"]["tags"] = [topic]
        update["understood"]["entry_signals"] = [topic]
    update["understood"]["artifact_type"] = artifact_type

    return update
