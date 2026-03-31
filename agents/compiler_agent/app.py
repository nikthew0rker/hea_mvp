from fastapi import FastAPI

from shared.schemas import CompileRequest, CompileResponse

app = FastAPI(title="Compiler Agent", version="0.2.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """
    Healthcheck endpoint for the Compiler Agent.
    """
    return {"status": "ok", "service": "compiler-agent"}


def _missing_feedback(draft: dict) -> list[str]:
    """
    Determine blocking problems for compilation.
    """
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


@app.post("/compile", response_model=CompileResponse)
async def compile_graph(payload: CompileRequest) -> CompileResponse:
    """
    Convert the current draft into a runtime-friendly graph artifact.
    """
    draft = payload.draft or {}
    feedback = _missing_feedback(draft)

    if feedback:
        return CompileResponse(
            status="invalid",
            graph_version_id=None,
            graph=None,
            feedback=feedback,
        )

    topic = (draft.get("understood", {}) or {}).get("topic", "assessment")
    graph_id = "graph_v1_demo"

    graph = {
        "graph_version_id": graph_id,
        "topic": topic,
        "target_audience": (draft.get("understood", {}) or {}).get("target_audience"),
        "questions": draft.get("candidate_questions", []) or [],
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
