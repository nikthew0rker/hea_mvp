from pydantic import BaseModel


class HealthResponse(BaseModel):
    """
    Common healthcheck response shape.
    """
    status: str
    service: str


class DraftRequest(BaseModel):
    """
    Input payload sent to the Definition Agent.

    The specialist bot will pass free-form text here.
    """
    specialist_text: str
    conversation_id: str


class DraftResponse(BaseModel):
    """
    Structured draft response returned by the Definition Agent.
    """
    conversation_id: str
    draft_status: str
    draft: dict
    clarification_question: str | None = None


class CompileRequest(BaseModel):
    """
    Input payload sent to the Compiler Agent.
    """
    draft: dict


class CompileResponse(BaseModel):
    """
    Output payload returned by the Compiler Agent.
    """
    status: str
    graph_version_id: str | None = None
    graph: dict | None = None
    feedback: list[str] = []


class RuntimeMessageRequest(BaseModel):
    """
    Input payload sent to the Runtime Agent from the User Bot.
    """
    conversation_id: str
    user_message: str
    active_graph_version_id: str


class RuntimeMessageResponse(BaseModel):
    """
    Output payload returned by the Runtime Agent.
    """
    conversation_id: str
    status: str
    reply_text: str
    session_state: dict
    should_generate_report: bool = False


class ReportRequest(BaseModel):
    """
    Input payload sent to the Report Agent.
    """
    session_state: dict
    graph: dict


class ReportResponse(BaseModel):
    """
    Output payload returned by the Report Agent.
    """
    short_summary: str
    full_report: dict


class EvalRequest(BaseModel):
    """
    Generic input payload for evaluation checks.
    """
    target_type: str
    payload: dict


class EvalResponse(BaseModel):
    """
    Generic evaluation result payload.
    """
    status: str
    checks: list[dict]
