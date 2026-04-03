import hashlib
import re

from fastapi import FastAPI

from shared.schemas import CompileRequest, CompileResponse

app = FastAPI(title="Compiler Agent", version="0.3.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "compiler-agent"}


def _missing_feedback(draft: dict) -> list[str]:
    feedback: list[str] = []

    understood = draft.get("understood", {}) or {}
    if not understood.get("topic"):
        feedback.append("Topic is missing")

    questions = draft.get("candidate_questions", []) or []
    if not questions:
        feedback.append("At least one question is required")

    scoring = draft.get("candidate_scoring_rules", {}) or {}
    if not scoring.get("method"):
        feedback.append("Scoring logic is missing")

    return feedback


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "assessment"


def _build_graph_id(topic: str, questions: list[dict]) -> str:
    seed = topic + "|" + "|".join(str(q.get("text", "")) for q in questions if isinstance(q, dict))
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"{_slugify(topic)}_{digest}"


@app.post("/compile", response_model=CompileResponse)
async def compile_graph(payload: CompileRequest) -> CompileResponse:
    draft = payload.draft or {}
    feedback = _missing_feedback(draft)

    if feedback:
        return CompileResponse(
            status="invalid",
            graph_version_id=None,
            graph=None,
            feedback=feedback,
        )

    understood = draft.get("understood", {}) or {}
    topic = understood.get("topic", "assessment")
    title = topic.replace("_", " ").title()

    questions = draft.get("candidate_questions", []) or []
    graph_id = _build_graph_id(str(topic), questions)

    graph = {
        "graph_version_id": graph_id,
        "title": title,
        "topic": topic,
        "target_audience": understood.get("target_audience"),
        "questions": questions,
        "risk_bands": draft.get("candidate_risk_bands", []) or [],
        "scoring": draft.get("candidate_scoring_rules", {}) or {},
        "report_rules": draft.get("candidate_report_requirements", []) or [],
        "safety_rules": draft.get("candidate_safety_requirements", []) or [],
        "source_draft": draft,
    }

    return CompileResponse(
        status="compiled",
        graph_version_id=graph_id,
        graph=graph,
        feedback=[],
    )
