from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hea.graphs.specialist.graph import build_specialist_graph
from hea.shared.api_models import ChatRequest, HealthResponse, SpecialistChatResponse
from hea.shared.db import init_db
from hea.shared.drafts import load_specialist_draft
from hea.shared.model_router import log_model_configuration_warnings
from hea.shared.runtime import infer_turn_language
from hea.shared.session_store import load_specialist_session, save_specialist_session


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log_model_configuration_warnings()
    app.state.graph = build_specialist_graph().compile()
    yield


app = FastAPI(title="Specialist Controller", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="specialist-controller")


@app.post("/chat", response_model=SpecialistChatResponse)
async def chat(payload: ChatRequest) -> SpecialistChatResponse:
    conversation_id = payload.conversation_id.strip() or "unknown"
    user_message = payload.user_message.strip()
    language = payload.language.strip()

    persisted_state = load_specialist_session(conversation_id)
    persisted_draft = load_specialist_draft(conversation_id)

    input_state = dict(persisted_state or {})
    input_state.update(
        {
            "conversation_id": conversation_id,
            "user_message": user_message,
            "draft": input_state.get("draft") or persisted_draft,
        }
    )
    if language:
        input_state["language"] = language
    else:
        input_state["language"] = infer_turn_language(user_message, str(input_state.get("language") or "en"))
    logger.info(
        "specialist_chat_start conversation_id=%s language=%s has_pending=%s",
        conversation_id,
        input_state.get("language") or "",
        bool(input_state.get("pending_proposal")),
    )

    try:
        result = await app.state.graph.ainvoke(input_state)
    except Exception:
        logger.exception("Specialist controller failed for conversation_id=%s", conversation_id)
        fallback_language = str(input_state.get("language") or "ru")
        reply_text = (
            "Внутренняя временная ошибка. Я сохранил текущий draft и могу продолжить работу после следующего сообщения."
            if fallback_language == "ru"
            else "Temporary internal error. I preserved the current draft and we can continue on the next message."
        )
        result = dict(input_state)
        result["assistant_reply"] = reply_text

    save_specialist_session(conversation_id, result)
    logger.info(
        "specialist_chat_end conversation_id=%s next_action=%s reply_len=%s",
        conversation_id,
        result.get("next_action"),
        len(str(result.get("assistant_reply") or "")),
    )

    return SpecialistChatResponse(
        reply_text=result.get("assistant_reply", ""),
        state=result,
    )
