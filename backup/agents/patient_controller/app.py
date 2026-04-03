from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from agents.patient_graph.graph import build_patient_graph
from shared.langgraph_runtime import open_async_sqlite_checkpointer


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with open_async_sqlite_checkpointer() as checkpointer:
        graph = build_patient_graph().compile(checkpointer=checkpointer)
        app.state.graph = graph
        yield


app = FastAPI(title="Patient Controller", version="2.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "patient-controller"}


@app.post("/chat")
async def chat(payload: dict):
    conversation_id = str(payload.get("conversation_id") or "unknown_conversation")
    user_message = str(payload.get("user_message") or "").strip()
    language = str(payload.get("language") or "")

    config = {"configurable": {"thread_id": conversation_id}}
    input_state = {
        "conversation_id": conversation_id,
        "user_message": user_message,
    }
    if language:
        input_state["language"] = language

    result = await app.state.graph.ainvoke(input_state, config=config)
    return {
        "status": result.get("mode", "free_conversation"),
        "reply_text": result.get("assistant_reply", ""),
        "session_state": result,
    }
