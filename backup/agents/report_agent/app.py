from fastapi import FastAPI

from shared.schemas import ReportRequest, ReportResponse

app = FastAPI(title="Report Agent", version="0.2.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """
    Healthcheck endpoint for the Report Agent.
    """
    return {"status": "ok", "service": "report-agent"}


@app.post("/generate", response_model=ReportResponse)
async def generate_report(payload: ReportRequest) -> ReportResponse:
    """
    Generate a lightweight patient summary from session state and graph payload.
    """
    session_state = payload.session_state or {}
    graph = payload.graph or {}

    answers = session_state.get("answers", []) or []
    score_total = session_state.get("score_total", 0)
    risk_band = session_state.get("risk_band") or {}

    topic = graph.get("topic") or graph.get("graph_version_id") or "assessment"
    risk_label = risk_band.get("label") if isinstance(risk_band, dict) else None

    if risk_label:
        short_summary = (
            f"Assessment topic: {topic}. "
            f"Completed answers: {len(answers)}. "
            f"Total score: {score_total}. "
            f"Risk category: {risk_label}."
        )
    else:
        short_summary = (
            f"Assessment topic: {topic}. "
            f"Completed answers: {len(answers)}. "
            f"Total score: {score_total}."
        )

    full_report = {
        "topic": topic,
        "answers_count": len(answers),
        "score_total": score_total,
        "risk_band": risk_band,
        "answers": answers,
    }

    return ReportResponse(
        short_summary=short_summary,
        full_report=full_report,
    )
