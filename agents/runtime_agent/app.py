from fastapi import FastAPI

from shared.schemas import RuntimeMessageRequest, RuntimeMessageResponse
from shared.together_client import TogetherAIClient

app = FastAPI(title="Runtime Agent", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    """
    Healthcheck endpoint for the Runtime Agent.
    """
    return {"status": "ok", "service": "runtime-agent"}


@app.post("/message", response_model=RuntimeMessageResponse)
async def process_user_message(payload: RuntimeMessageRequest) -> RuntimeMessageResponse:
    """
    Process one user message in a graph-driven conversational flow.

    This scaffold keeps the state model deliberately small:
    - one reply text
    - one minimal session state object
    - one flag indicating whether report generation should start
    """
    llm = TogetherAIClient()

    system_prompt = (
        "You are a runtime assessment agent. "
        "Reply briefly and conversationally. "
        "Do not diagnose, prescribe treatment, or recommend medication. "
        "Collect information and keep the interaction natural."
    )

    user_prompt = payload.user_message
    reply_text = await llm.complete(system_prompt, user_prompt)

    session_state = {
        "conversation_id": payload.conversation_id,
        "graph_version_id": payload.active_graph_version_id,
        "last_user_message": payload.user_message,
        "last_agent_reply": reply_text,
    }

    should_generate_report = "done" in payload.user_message.lower()

    return RuntimeMessageResponse(
        conversation_id=payload.conversation_id,
        status="in_progress" if not should_generate_report else "completed",
        reply_text=reply_text,
        session_state=session_state,
        should_generate_report=should_generate_report,
    )
