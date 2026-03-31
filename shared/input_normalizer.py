import re
from typing import Any


NOISE_PATTERNS = [
    r"^https?://",
    r"^\+?\d[\d\s\-\(\)]{6,}$",
    r"^\s*тел",
    r"^\s*phone",
    r"^\s*контакты",
    r"^\s*главная",
    r"^\s*search",
    r"^\s*menu",
    r"^\s*navigation",
    r"^\s*читать далее"
]

MEDICAL_TOPIC_KEYWORDS = {
    "diabetes": ["диабет", "diabetes", "глюкоз", "hba1c", "сахарн"],
    "sleep": ["сон", "sleep", "insomnia", "бессон", "sleepiness"],
    "stress": ["stress", "стресс", "anxiety", "тревог"],
    "cardio": ["сердц", "cardio", "blood pressure", "давлен"]
}


def detect_language(text: str) -> str:
    """
    Pragmatic Russian/English language detection for chat turns.
    """
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "ru"
    if re.search(r"[a-zA-Z]", text):
        return "en"
    return "en"


def normalize_specialist_input(text: str) -> dict[str, Any]:
    """
    Clean noisy pasted text and extract weak structure before LLM extraction.
    """
    original_lines = text.splitlines()
    cleaned_lines: list[str] = []
    removed_lines: list[str] = []

    for raw_line in original_lines:
        line = raw_line.strip()
        if not line:
            continue

        if _is_noise_line(line):
            removed_lines.append(line)
            continue

        cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines)
    detected_shape = detect_input_shape(cleaned_text)

    return {
        "language": detect_language(text),
        "cleaned_text": cleaned_text,
        "detected_shape": detected_shape,
        "removed_noise_lines_count": len(removed_lines),
        "heuristic_candidates": {
            "topic": infer_topic(cleaned_text),
            "questions": extract_numbered_questions(cleaned_text),
            "risk_bands": extract_risk_bands(cleaned_text),
            "scoring_logic": infer_scoring_logic(cleaned_text)
        }
    }


def detect_input_shape(text: str) -> str:
    """
    Detect the rough shape of the specialist input.
    """
    if len(re.findall(r"^\d+[\)\.\- ]", text, flags=re.MULTILINE)) >= 3:
        return "questionnaire_scale"

    if len(re.findall(r"\d+\s*[-–]\s*\d+", text)) >= 2:
        return "score_table_or_risk_bands"

    if len(text.splitlines()) > 12:
        return "long_noisy_document"

    return "free_text"


def infer_topic(text: str) -> str | None:
    """
    Infer a coarse medical topic from keywords.
    """
    t = text.lower()
    for label, keywords in MEDICAL_TOPIC_KEYWORDS.items():
        if any(keyword in t for keyword in keywords):
            return label
    return None


def extract_numbered_questions(text: str) -> list[dict]:
    """
    Extract numbered questions from questionnaire-like content.
    """
    questions: list[dict] = []
    seen: set[str] = set()

    for line in text.splitlines():
        match = re.match(r"^\s*(\d+)[\)\.\- ]+\s*(.+)$", line)
        if not match:
            continue

        question_text = match.group(2).strip()
        if len(question_text) < 4:
            continue

        qid = f"q{match.group(1)}"
        if qid in seen:
            continue

        seen.add(qid)
        questions.append(
            {
                "id": qid,
                "text": question_text,
                "question_type": "single_choice",
                "options": [],
                "notes": None
            }
        )

    return questions


def extract_risk_bands(text: str) -> list[dict]:
    """
    Extract score ranges and labels from text.
    """
    bands: list[dict] = []

    for line in text.splitlines():
        match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*[:\-]?\s*(.+)", line)
        if not match:
            continue

        min_score = float(match.group(1))
        max_score = float(match.group(2))
        tail = match.group(3).strip()

        if len(tail) < 2:
            continue

        label = tail.split(",")[0].split(".")[0].strip()
        bands.append(
            {
                "min_score": min_score,
                "max_score": max_score,
                "label": label,
                "meaning": tail
            }
        )

    return bands


def infer_scoring_logic(text: str) -> dict:
    """
    Infer a basic scoring rule from score-like content.
    """
    t = text.lower()
    if "балл" in t or "score" in t or len(re.findall(r"\d+\s*[-–]\s*\d+", t)) >= 2:
        return {
            "method": "sum_of_item_scores",
            "notes": "heuristically inferred from score-like content"
        }
    return {}


def _is_noise_line(line: str) -> bool:
    """
    Detect obvious webpage/navigation noise.
    """
    low = line.lower()
    if len(low) <= 2:
        return True

    for pattern in NOISE_PATTERNS:
        if re.search(pattern, low):
            return True

    return False
