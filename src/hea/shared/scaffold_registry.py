from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


Scaffold = dict[str, Any]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = PROJECT_ROOT / "config" / "scaffold_strategies.json"


def normalize_scaffold_text(text: str | None) -> str:
    return " ".join(str(text or "").lower().strip().split())


def infer_scaffold_topic(raw: str | None) -> str | None:
    low = normalize_scaffold_text(raw)
    if not low:
        return None
    if any(token in low for token in ["diabet", "diabets", "diabetes", "диабет", "findrisk"]):
        return "diabetes"
    if any(token in low for token in ["sleep", "сон", "insomnia"]):
        return "sleep"
    if any(token in low for token in ["stress", "стресс", "burnout", "выгорание"]):
        return "stress"
    return None


def infer_scaffold_framework(raw: str | None) -> str | None:
    low = normalize_scaffold_text(raw)
    if "findrisk" in low:
        return "findrisk"
    if "burnout" in low or "выгорание" in low:
        return "burnout"
    return None


def looks_like_findrisk_questionnaire(
    topic: str | None,
    framework: str | None,
    questions: list[dict[str, Any]] | None = None,
    raw_text: str | None = None,
) -> bool:
    low_topic = normalize_scaffold_text(topic)
    low_framework = normalize_scaffold_text(framework)
    low_text = normalize_scaffold_text(raw_text)
    if low_framework == "findrisk" or "findrisk" in low_text:
        return True
    if "diabet" not in low_topic and "diabet" not in low_text and "диабет" not in low_text:
        return False

    question_texts = " ".join(
        normalize_scaffold_text(question.get("text"))
        for question in (questions or [])
        if isinstance(question, dict)
    )
    combined = f"{low_text} {question_texts}".strip()
    cues = [
        any(token in combined for token in ["age", "возраст"]),
        any(token in combined for token in ["body mass index", "bmi", "индекс массы тела", "имт"]),
        any(token in combined for token in ["waist circumference", "окружность талии"]),
        any(token in combined for token in ["physical activity", "exercise", "физичес", "упражнен"]),
        any(token in combined for token in ["vegetables", "fruit", "berries", "овощ", "фрукт", "ягод"]),
        any(token in combined for token in ["antihypertensive", "гипотензив", "blood pressure medication"]),
        any(token in combined for token in ["blood glucose", "glucose", "глюкоз", "сахар"]),
        any(token in combined for token in ["family history", "членов семьи", "родствен", "diabetes in family"]),
    ]
    return len(questions or []) >= 5 and sum(cues) >= 4


def _load_catalog_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"strategies": []}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {"strategies": []}


def _normalize_strategy(raw: dict[str, Any]) -> dict[str, Any] | None:
    strategy_id = str(raw.get("strategy_id") or "").strip()
    topic = str(raw.get("topic") or "").strip()
    if not strategy_id or not topic:
        return None

    framework = raw.get("framework")
    framework = str(framework).strip() if framework is not None and str(framework).strip() else None
    scaffold = raw.get("scaffold")
    if not isinstance(scaffold, dict):
        return None

    normalized = deepcopy(scaffold)
    understood = dict(normalized.get("understood") or {})
    understood.setdefault("topic", topic)
    if framework:
        understood.setdefault("framework", framework)
    normalized["understood"] = understood

    proposal_meta = dict(normalized.get("_proposal_meta") or {})
    proposal_meta.setdefault("source_type", "starter_template")
    proposal_meta.setdefault("strategy_id", strategy_id)
    if raw.get("question_source_summary"):
        proposal_meta.setdefault("question_source_summary", str(raw["question_source_summary"]))
    normalized["_proposal_meta"] = proposal_meta

    return {
        "strategy_id": strategy_id,
        "topic": topic,
        "framework": framework,
        "question_source_summary": str(raw.get("question_source_summary") or proposal_meta.get("question_source_summary") or strategy_id),
        "scaffold": normalized,
    }


@lru_cache(maxsize=1)
def load_scaffold_catalog() -> dict[tuple[str, str | None], dict[str, Any]]:
    raw_catalog = _load_catalog_file(CATALOG_PATH)
    raw_strategies = raw_catalog.get("strategies") or []

    catalog: dict[tuple[str, str | None], dict[str, Any]] = {}
    for raw in raw_strategies:
        if not isinstance(raw, dict):
            continue
        normalized = _normalize_strategy(raw)
        if not normalized:
            continue
        key = (normalized["topic"], normalized["framework"])
        catalog[key] = normalized
    return catalog


def reload_scaffold_catalog() -> None:
    load_scaffold_catalog.cache_clear()


def get_scaffold(topic: str | None, framework: str | None = None) -> Scaffold:
    if not topic:
        return {}
    catalog = load_scaffold_catalog()
    strategy = catalog.get((topic, framework)) or catalog.get((topic, None))
    if not strategy:
        return {}
    return deepcopy(strategy["scaffold"])
