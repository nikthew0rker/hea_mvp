from pydantic import BaseModel, Field


class AnswerOption(BaseModel):
    label: str
    score: float | None = None
    notes: str | None = None


class CandidateQuestion(BaseModel):
    id: str
    text: str
    question_type: str = "single_choice"
    options: list[AnswerOption] = Field(default_factory=list)
    notes: str | None = None


class CandidateRiskBand(BaseModel):
    min_score: float
    max_score: float
    label: str
    meaning: str | None = None


class CandidateRequirement(BaseModel):
    title: str
    instruction: str


class DraftRequest(BaseModel):
    specialist_text: str
    conversation_id: str
    current_draft: dict | None = None
    current_language: str | None = None
    conversation_summary: str | None = None
    operation: str = "update"


class DraftResponse(BaseModel):
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
    draft: dict


class CompileResponse(BaseModel):
    status: str
    graph_version_id: str | None = None
    graph: dict | None = None
    feedback: list[str] = Field(default_factory=list)


class RuntimeMessageRequest(BaseModel):
    conversation_id: str
    user_message: str
    active_graph_version_id: str


class RuntimeMessageResponse(BaseModel):
    conversation_id: str
    status: str
    reply_text: str
    session_state: dict
    should_generate_report: bool = False


class ReportRequest(BaseModel):
    session_state: dict
    graph: dict


class ReportResponse(BaseModel):
    short_summary: str
    full_report: dict


class EvalRequest(BaseModel):
    target_type: str
    payload: dict


class EvalResponse(BaseModel):
    status: str
    checks: list[dict]
