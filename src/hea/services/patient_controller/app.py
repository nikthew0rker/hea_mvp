from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response

from hea.graphs.patient.graph import build_patient_graph
from hea.shared.api_models import ChatRequest, HealthResponse, PatientChatResponse
from hea.shared.db import init_db
from hea.shared.model_router import log_model_configuration_warnings
from hea.shared.runtime import infer_turn_language, render_report_html, render_report_pdf
from hea.shared.session_store import load_patient_session, save_patient_session

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log_model_configuration_warnings()
    app.state.graph = build_patient_graph().compile()
    yield


app = FastAPI(title="Patient Controller", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="patient-controller")


@app.post("/chat", response_model=PatientChatResponse)
async def chat(payload: ChatRequest) -> PatientChatResponse:
    conversation_id = payload.conversation_id.strip() or "unknown"
    user_message = payload.user_message.strip()
    language = payload.language.strip()

    persisted_state = load_patient_session(conversation_id)
    input_state = dict(persisted_state or {})
    input_state.update(
        {
            "conversation_id": conversation_id,
            "user_message": user_message,
        }
    )
    if language:
        input_state["language"] = language
    else:
        input_state["language"] = infer_turn_language(user_message, str(input_state.get("language") or "en"))
    logger.info(
        "patient_chat_start conversation_id=%s language=%s mode=%s",
        conversation_id,
        input_state.get("language") or "",
        input_state.get("mode") or "free_conversation",
    )

    try:
        result = await app.state.graph.ainvoke(input_state)
    except Exception:
        logger.exception("Patient controller failed for conversation_id=%s", conversation_id)
        fallback_language = str(input_state.get("language") or "ru")
        result = dict(input_state)
        result["assistant_reply"] = (
            "Внутренняя временная ошибка. Я сохранил текущий контекст и могу продолжить после следующего сообщения."
            if fallback_language == "ru"
            else "Temporary internal error. I preserved the current context and we can continue on the next message."
        )

    # promote runtime completion into post_assessment mode
    assessment_state = result.get("assessment_state")
    if isinstance(assessment_state, dict) and assessment_state.get("status") == "completed":
        result["mode"] = "post_assessment"
        result["last_result"] = assessment_state.get("result")

    save_patient_session(conversation_id, result)
    logger.info(
        "patient_chat_end conversation_id=%s mode=%s reply_len=%s",
        conversation_id,
        result.get("mode", "free_conversation"),
        len(str(result.get("assistant_reply") or "")),
    )

    return PatientChatResponse(
        status=result.get("mode", "free_conversation"),
        reply_text=result.get("assistant_reply", ""),
        state=result,
    )


@app.get("/report/{conversation_id}.pdf")
async def report_pdf(conversation_id: str) -> Response:
    state = load_patient_session(conversation_id) or {}
    language = str(state.get("language") or "en")
    assessment_state = state.get("assessment_state") or {}
    result = assessment_state.get("result") or state.get("last_result")
    if isinstance(result, dict):
        result = dict(result)
        result["_graph"] = state.get("selected_graph") or {}
        result["_answers"] = (assessment_state.get("answers") if isinstance(assessment_state, dict) else None) or []
    return Response(
        content=render_report_pdf(result, language),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename=\"{conversation_id}.pdf\"'},
    )


@app.get("/report/{conversation_id}", response_class=HTMLResponse)
async def report(conversation_id: str) -> HTMLResponse:
    state = load_patient_session(conversation_id) or {}
    language = str(state.get("language") or "en")
    assessment_state = state.get("assessment_state") or {}
    result = assessment_state.get("result") or state.get("last_result")
    if isinstance(result, dict):
        result = dict(result)
        result["_graph"] = state.get("selected_graph") or {}
        result["_answers"] = (assessment_state.get("answers") if isinstance(assessment_state, dict) else None) or []
    return HTMLResponse(render_report_html(result, language))
