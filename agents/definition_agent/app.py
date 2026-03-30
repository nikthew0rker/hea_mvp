from fastapi import FastAPI

from shared.schemas import DraftRequest, DraftResponse
from shared.together_client import TogetherAIClient

app = FastAPI(title="Definition Agent", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    """
    Healthcheck endpoint for the Definition Agent.
    """
    return {"status": "ok", "service": "definition-agent"}


@app.post("/draft", response_model=DraftResponse)
async def build_draft(payload: DraftRequest) -> DraftResponse:
    """
    Convert free-form specialist text into a structured draft.

    In this scaffold, the agent asks Together AI to return a lightweight draft.
    The output is intentionally permissive and should be tightened later.
    """
    llm = TogetherAIClient()

    system_prompt = (
        "You are a definition structuring agent. "
        "Convert specialist text into a JSON-like assessment draft with fields: "
        "title, goal, questions, scoring, risk_bands, report, safety. "
        "If information is missing, keep empty fields and propose one clarification question."
    )

    user_prompt = payload.specialist_text
    model_text = await llm.complete(system_prompt, user_prompt)

    draft = {
        "raw_model_output": model_text,
        "source_text": payload.specialist_text,
    }

    return DraftResponse(
        conversation_id=payload.conversation_id,
        draft_status="needs_review",
        draft=draft,
        clarification_question="What should be the exact scoring logic and risk bands?",
    )
