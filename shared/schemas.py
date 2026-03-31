from pydantic import BaseModel, Field


class AnswerOption(BaseModel):
    """
    One answer option candidate extracted from specialist content.
    """
    label: str
    score: float | None = None
    notes: str | None = None


class CandidateQuestion(BaseModel):
    """
    A normalized assessment question candidate.
    """
    id: str
    text: str
    question_type: str = "single_choice"
    options: list[AnswerOption] = Field(default_factory=list)
    notes: str | None = None


class CandidateRiskBand(BaseModel):
    """
    A risk band candidate extracted from source material.
    """
    min_score: float
    max_score: float
    label: str
    meaning: str | None = None


class CandidateRequirement(BaseModel):
    """
    Generic report/safety requirement item.
    """
    title: str
    instruction: str


class DraftRequest(BaseModel):
    """
    Input payload for the Definition Agent.

    operation:
    - update: interpret new source material and merge it into the draft
    - edit: apply a natural-language edit instruction to the existing draft
    """
    specialist_text: str
    conversation_id: str
    current_draft: dict | None = None
    current_language: str | None = None
    conversation_summary: str | None = None
    operation: str = "update"


class DraftResponse(BaseModel):
    """
    Structured internal state returned by the Definition Agent.
    """
    conversation_id: str
    status: str
    language: str
    understood: dict = Field(default_factory=dict)

    candidate_questions: list[CandidateQuestion] = Field(default_factory=list)
    candidate_scoring_rules: dict = Field(default_factory=dict)
    candidate_risk_bands: list[CandidateRiskBand] = Field(default_factory=list)
    candidate_report_requirements: list[CandidateRequirement] = Field(default_factory=list)
    candidate_safety_requirements: list[CandidateRequirement] = Field(default_factory=list)

    missing_fields: list[str] = Field(default_factory=list)
    suggested_next_question: str | None = None
    draft: dict = Field(default_factory=dict)


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
    feedback: list[str] = Field(default_factory=list)


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
