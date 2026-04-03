from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QuestionOptionSpec(BaseModel):
    label: str
    value: str
    score: float = 0.0
    condition: str | None = None
    source_excerpt: str | None = None
    next_question_id: str | None = None


class QuestionSpec(BaseModel):
    id: str
    text: str
    question_type: Literal["single_choice", "multi_choice", "number", "text"] = "single_choice"
    source: str | None = None
    source_excerpt: str | None = None
    source_line_range: str | None = None
    options: list[QuestionOptionSpec] = Field(default_factory=list)
    notes: str | None = None


class RiskBandSpec(BaseModel):
    min_score: float
    max_score: float
    label: str
    meaning: str | None = None
    source_excerpt: str | None = None


class AnamnesisSectionSpec(BaseModel):
    id: str
    title: str
    goal: str | None = None
    source_excerpt: str | None = None
    questions: list[QuestionSpec] = Field(default_factory=list)
    branching_cues: list[str] = Field(default_factory=list)


class ClinicalRuleNodeSpec(BaseModel):
    id: str
    label: str
    condition: str | None = None
    conditions_ast: list[dict[str, str]] = Field(default_factory=list)
    outcome: str | None = None
    next_node_id: str | None = None
    source: str | None = None
    source_excerpt: str | None = None


class QuestionnaireSpec(BaseModel):
    artifact_type: Literal["questionnaire", "anamnesis_flow", "clinical_rule_graph"] = "questionnaire"
    topic: str | None = None
    framework: str | None = None
    title: str | None = None
    description: str | None = None
    target_population: str | None = None
    questions: list[QuestionSpec] = Field(default_factory=list)
    scoring_method: str | None = None
    risk_bands: list[RiskBandSpec] = Field(default_factory=list)
    anamnesis_sections: list[AnamnesisSectionSpec] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    assessment_output: str | None = None
    report_requirements: list[str] = Field(default_factory=list)
    diagnostic_inputs: list[str] = Field(default_factory=list)
    rule_nodes: list[ClinicalRuleNodeSpec] = Field(default_factory=list)
    conclusion_template: str | None = None
    source_excerpt: str | None = None


class EditOperation(BaseModel):
    intent_type: Literal[
        "discuss",
        "replace_questions_from_text",
        "append_questions_from_text",
        "replace_risk_bands",
        "add_anamnesis_section",
        "replace_rule_nodes",
        "replace_description",
        "regenerate_description",
        "set_framework",
        "show_diff",
        "show_versions",
        "rollback_draft",
        "show_preview",
        "show_detailed_draft",
        "show_questions",
        "show_scoring",
        "show_risks",
        "explain_question_source",
        "compile",
        "publish",
        "apply_pending_proposal",
        "apply_questions_only",
        "apply_risks_only",
        "apply_sections_only",
        "apply_rules_only",
        "help",
    ] = "discuss"
    target_section: str | None = None
    requires_compilation: bool = False
    requires_confirmation: bool = True
    framework: str | None = None
    rationale: str | None = None
    clarification_question: str | None = None
    rollback_version_id: int | None = None


class ValidationFinding(BaseModel):
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    field_path: str | None = None


class CriticReview(BaseModel):
    is_valid: bool = True
    severity: Literal["info", "warning", "error"] = "warning"
    findings: list[ValidationFinding] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    proposed_repairs: list[str] = Field(default_factory=list)
    should_block_apply: bool = False


class PendingProposal(BaseModel):
    operation: EditOperation
    spec: QuestionnaireSpec
    review: CriticReview
    source_message: str
