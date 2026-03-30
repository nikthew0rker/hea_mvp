from fastapi import FastAPI

from shared.schemas import ReportRequest, ReportResponse
from shared.together_client import TogetherAIClient

app = FastAPI(title="Report Agent", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    """
    Healthcheck endpoint for the Report Agent.
    """
    return {"status": "ok", "service": "report-agent"}


@app.post("/generate", response_model=ReportResponse)
async def generate_report(payload: ReportRequest) -> ReportResponse:
    """
    Build the final user-facing result.

    The scaffold produces:
    - a short Telegram-safe summary
    - a fuller structured report object
    """
    llm = TogetherAIClient()

    system_prompt = (
        "You are a report generation agent. "
        "Produce a short, non-diagnostic, user-friendly summary. "
        "Include a disclaimer. "
        "Do not prescribe treatment or medication."
    )

    user_prompt = (
        f"Session state:\n{payload.session_state}\n\n"
        f"Graph:\n{payload.graph}\n\n"
        "Write a concise summary for Telegram."
    )

    short_summary = await llm.complete(system_prompt, user_prompt)

    full_report = {
        "summary": short_summary,
        "disclaimer": (
            "This assessment is informational only and does not provide a medical diagnosis, "
            "treatment plan, or medication recommendation."
        ),
        "session_state": payload.session_state,
        "graph_version_id": payload.graph.get("graph_version_id"),
    }

    return ReportResponse(
        short_summary=short_summary,
        full_report=full_report,
    )
