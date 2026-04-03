from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hea.shared.authoring_pipeline import compile_questionnaire_spec  # noqa: E402
from hea.shared.authoring_models import EditOperation  # noqa: E402
from hea.shared.authoring_pipeline import plan_edit_operation  # noqa: E402
from hea.graphs.specialist.nodes import (  # noqa: E402
    apply_pending_proposal,
    compile_draft,
    discuss_specialist_goal,
    explain_question_source,
    publish_draft,
    reset_and_help,
    rollback_draft,
    route_specialist_message,
    show_diff,
    show_detailed_draft,
    show_help,
    show_preview,
    show_versions,
    update_draft,
)
from hea.shared.drafts import save_specialist_draft_version  # noqa: E402
from hea.shared.models import compile_graph_from_draft, default_draft  # noqa: E402


class SpecialistFlowTests(unittest.TestCase):
    def test_start_help_describes_supported_graph_types(self) -> None:
        result = asyncio.run(reset_and_help({"language": "ru"}))
        self.assertIn("questionnaire", result["assistant_reply"])
        self.assertIn("anamnesis_flow", result["assistant_reply"])
        self.assertIn("clinical_rule_graph", result["assistant_reply"])
        self.assertIn("`publish`", result["assistant_reply"])

    def test_show_help_adds_pending_proposal_hint(self) -> None:
        result = asyncio.run(show_help({"language": "ru", "pending_proposal": {"spec": {"topic": "diabetes"}}}))
        self.assertIn("подготовленное предложение", result["assistant_reply"])
        self.assertIn("`примени предложение`", result["assistant_reply"])

    def test_specialist_language_follows_current_user_turn(self) -> None:
        pending = {
            "operation": {
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "requires_confirmation": True,
                "framework": None,
                "rationale": None,
                "clarification_question": None,
                "rollback_version_id": None,
            },
            "spec": {
                "artifact_type": "questionnaire",
                "topic": "diabetes",
                "framework": None,
                "title": None,
                "description": "draft",
                "target_population": None,
                "questions": [{"id": "q1", "text": "Age", "question_type": "single_choice", "source": "source", "options": [{"label": "A", "value": "a", "score": 0}], "notes": None}],
                "scoring_method": "sum_of_option_scores",
                "risk_bands": [],
                "anamnesis_sections": [],
                "red_flags": [],
                "assessment_output": None,
                "diagnostic_inputs": [],
                "rule_nodes": [],
                "conclusion_template": None,
                "source_excerpt": "source",
            },
            "review": {
                "is_valid": True,
                "severity": "info",
                "findings": [],
                "missing_information": [],
                "proposed_repairs": [],
                "should_block_apply": False,
            },
            "source_message": "source",
        }
        routed = asyncio.run(route_specialist_message({"language": "ru", "user_message": "yes", "pending_proposal": pending}))
        self.assertEqual(routed["language"], "en")
        applied = asyncio.run(apply_pending_proposal({"language": routed["language"], "conversation_id": "lang_switch", "draft": default_draft(), "pending_proposal": pending}))
        self.assertIn("Applied the proposal", applied["assistant_reply"])

    def test_goal_statement_creates_pending_proposal(self) -> None:
        state = {"language": "ru", "draft": default_draft(), "user_message": "я хочу собрать findrisk диабета"}
        routed = asyncio.run(route_specialist_message(state))
        self.assertEqual(routed["next_action"], "DISCUSS")
        self.assertTrue(routed["analyst_decision"]["should_prepare_proposal"])

        result = asyncio.run(discuss_specialist_goal({**state, **routed}))
        self.assertIn("не применял", result["assistant_reply"].lower())
        self.assertIn("pending_proposal", result)
        self.assertEqual(len(result["pending_proposal"]["spec"]["questions"]), 8)

    def test_free_form_message_keeps_discussion_mode(self) -> None:
        state = {"language": "ru", "draft": default_draft(), "user_message": "хочу сценарий анамнеза по диабету, но вопросы задам сам позже"}
        routed = asyncio.run(route_specialist_message(state))
        self.assertEqual(routed["next_action"], "DISCUSS")
        self.assertIn("analyst_decision", routed)
        self.assertGreaterEqual(routed["analyst_decision"]["confidence"], 0.6)

    def test_random_noise_does_not_zero_existing_draft(self) -> None:
        existing_draft = {
            "understood": {"topic": "diabetes", "description": "existing"},
            "candidate_questions": [{"id": "q1", "text": "Возраст", "source": "starter"}],
            "candidate_scoring_rules": {"method": "sum_of_option_scores"},
            "candidate_risk_bands": [{"min_score": 0, "max_score": 1, "label": "Low"}],
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        state = {"language": "ru", "draft": existing_draft, "user_message": "опапап"}
        routed = asyncio.run(route_specialist_message(state))
        self.assertEqual(routed["next_action"], "DISCUSS")

        result = asyncio.run(discuss_specialist_goal({**state, **routed}))
        self.assertNotIn("draft", result)
        self.assertIn("не менял draft автоматически", result["assistant_reply"])
        self.assertIn("`compile`, потом `publish`", result["assistant_reply"])

    def test_show_detailed_draft_explains_question_sources(self) -> None:
        draft = {
            "understood": {"topic": "diabetes", "description": "topic", "framework": "findrisk"},
            "candidate_questions": [{"id": "q1", "text": "Возраст", "source": "starter FINDRISC-like scaffold"}],
            "candidate_scoring_rules": {"method": "sum_of_option_scores"},
            "candidate_risk_bands": [{"min_score": 0, "max_score": 1, "label": "Low"}],
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        result = asyncio.run(show_detailed_draft({"language": "ru", "draft": draft}))
        self.assertIn("source: starter FINDRISC-like scaffold", result["assistant_reply"])

        source_result = asyncio.run(explain_question_source({"language": "ru", "draft": draft}))
        self.assertIn("Источники вопросов", source_result["assistant_reply"])

    def test_apply_pending_proposal_updates_draft(self) -> None:
        pending = {
            "operation": {
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "requires_confirmation": True,
                "framework": None,
                "rationale": None,
                "clarification_question": None,
            },
            "spec": {
                "topic": "sleep",
                "framework": None,
                "title": None,
                "description": "sleep draft",
                "target_population": None,
                "questions": [{"id": "q1", "text": "Sleep?", "question_type": "single_choice", "source": "starter", "options": [], "notes": None}],
                "scoring_method": "sum_of_option_scores",
                "risk_bands": [{"min_score": 0, "max_score": 1, "label": "Low", "meaning": None}],
                "source_excerpt": "sleep",
            },
            "review": {
                "is_valid": True,
                "severity": "info",
                "findings": [],
                "missing_information": [],
                "proposed_repairs": [],
                "should_block_apply": False,
            },
            "source_message": "sleep",
        }
        result = asyncio.run(
            apply_pending_proposal(
                {
                    "language": "ru",
                    "conversation_id": "test",
                    "draft": default_draft(),
                    "pending_proposal": pending,
                }
            )
        )
        self.assertEqual(result["draft"]["understood"]["topic"], "sleep")
        self.assertIsNone(result["pending_proposal"])

    def test_compiler_preserves_scored_options_from_numbered_block(self) -> None:
        source = """
1. Возраст
- <45 лет — 0 баллов
- 45–54 лет — 2 балла
- 55–64 лет — 3 балла
- >64 лет — 4 балла
""".strip()
        operation = EditOperation(intent_type="replace_questions_from_text", target_section="questions", requires_compilation=True)
        spec = asyncio.run(compile_questionnaire_spec(source, default_draft(), operation, "ru"))
        self.assertEqual(len(spec.questions), 1)
        self.assertEqual(len(spec.questions[0].options), 4)
        self.assertEqual(spec.questions[0].options[1].score, 2.0)
        self.assertNotEqual({option.label.lower() for option in spec.questions[0].options}, {"yes", "no"})

    def test_compiler_preserves_demographic_option_conditions(self) -> None:
        source = """
1. Окружность талии
Для мужчин:
- <94 см — 0 баллов
- 94–102 см — 3 балла
Для женщин:
- <80 см — 0 баллов
- 80–88 см — 3 балла
""".strip()
        operation = EditOperation(intent_type="replace_questions_from_text", target_section="questions", requires_compilation=True)
        spec = asyncio.run(compile_questionnaire_spec(source, default_draft(), operation, "ru"))
        self.assertEqual(len(spec.questions), 1)
        self.assertEqual(len(spec.questions[0].options), 4)
        conditions = [option.condition for option in spec.questions[0].options]
        self.assertIn("Для мужчин", conditions)
        self.assertIn("Для женщин", conditions)

    def test_anamnesis_goal_creates_anamnesis_flow_proposal(self) -> None:
        state = {
            "language": "ru",
            "draft": default_draft(),
            "user_message": "хочу собрать анамнез по боли в груди\n1. Когда началась боль?\n2. Есть ли одышка?\n- Да\n- Нет",
        }
        routed = asyncio.run(route_specialist_message(state))
        result = asyncio.run(discuss_specialist_goal({**state, **routed}))
        self.assertEqual(result["pending_proposal"]["spec"]["artifact_type"], "anamnesis_flow")
        self.assertEqual(len(result["pending_proposal"]["spec"]["anamnesis_sections"]), 1)

    def test_clinical_rule_goal_creates_rule_graph_proposal(self) -> None:
        source = """
нужна клиническая схема раннего выявления диабета
1. Глюкоза натощак
- <5.6 — 0 баллов
- 5.6-6.9 — 1 балл
- >=7.0 — 2 балла
2. HbA1c
- <5.7 — 0 баллов
- 5.7-6.4 — 1 балл
- >=6.5 — 2 балла
""".strip()
        operation = EditOperation(intent_type="replace_questions_from_text", target_section="rule_nodes", requires_compilation=True)
        spec = asyncio.run(compile_questionnaire_spec(source, default_draft(), operation, "ru"))
        self.assertEqual(spec.artifact_type, "clinical_rule_graph")
        self.assertGreaterEqual(len(spec.diagnostic_inputs), 2)
        self.assertGreaterEqual(len(spec.rule_nodes), 2)

    def test_explicit_if_then_rules_become_rule_nodes(self) -> None:
        source = """
если глюкоза натощак >= 7.0, то высокий риск диабета
если HbA1c >= 6.5, то вероятен диабет 2 типа
""".strip()
        operation = EditOperation(intent_type="replace_rule_nodes", target_section="rule_nodes", requires_compilation=True)
        spec = asyncio.run(compile_questionnaire_spec(source, default_draft(), operation, "ru"))
        self.assertEqual(spec.artifact_type, "clinical_rule_graph")
        self.assertEqual(len(spec.rule_nodes), 2)
        self.assertIn("глюкоза натощак >= 7.0", spec.rule_nodes[0].condition or "")
        self.assertIn("высокий риск диабета", spec.rule_nodes[0].outcome or "")
        self.assertTrue(spec.rule_nodes[0].conditions_ast)

    def test_compile_graph_adds_runtime_questions_for_rule_graph(self) -> None:
        draft = {
            "understood": {"topic": "diabetes", "artifact_type": "clinical_rule_graph"},
            "candidate_questions": [],
            "candidate_scoring_rules": {},
            "candidate_risk_bands": [],
            "candidate_anamnesis_sections": [],
            "candidate_red_flags": [],
            "candidate_assessment_output": None,
            "candidate_diagnostic_inputs": ["Глюкоза натощак", "HbA1c"],
            "candidate_rule_nodes": [{"id": "rule_1", "label": "Высокий риск", "condition": "Глюкоза натощак >= 7.0", "conditions_ast": [{"field": "Глюкоза натощак", "operator": ">=", "value": "7.0"}], "outcome": "Высокий риск диабета"}],
            "candidate_conclusion_template": None,
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        compiled = compile_graph_from_draft(draft)
        self.assertEqual(compiled["status"], "compiled")
        self.assertEqual(compiled["graph"]["artifact_type"], "clinical_rule_graph")
        self.assertEqual(len(compiled["graph"]["questions"]), 2)

    def test_risk_band_update_keeps_questionnaire_context(self) -> None:
        source = """
Суммируются все баллы по вопросам 1–8.

Интерпретация суммы баллов:
- <7 — низкий риск, вероятность 1%
- 7–11 — слегка повышен, вероятность 4%
- 12–14 — умеренный риск, вероятность 17%
- 15–20 — высокий риск, вероятность 33%
- >20 — очень высокий риск, вероятность 50%
""".strip()
        draft = {
            "understood": {"topic": "diabetes", "artifact_type": "questionnaire"},
            "candidate_questions": [{"id": "q1", "text": "Возраст", "question_type": "single_choice", "options": [{"label": "<45", "value": "1", "score": 0}], "source": "starter"}],
            "candidate_scoring_rules": {"method": "sum_of_option_scores"},
            "candidate_risk_bands": [],
            "candidate_anamnesis_sections": [],
            "candidate_red_flags": [],
            "candidate_assessment_output": None,
            "candidate_diagnostic_inputs": [],
            "candidate_rule_nodes": [],
            "candidate_conclusion_template": None,
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        operation = EditOperation(intent_type="replace_risk_bands", target_section="risk_bands", requires_compilation=True)
        spec = asyncio.run(compile_questionnaire_spec(source, draft, operation, "ru"))
        self.assertEqual(spec.artifact_type, "questionnaire")
        self.assertEqual(len(spec.risk_bands), 5)
        self.assertEqual(spec.risk_bands[0].label, "низкий риск")
        self.assertEqual(spec.risk_bands[-1].label, "очень высокий риск")

    def test_burnout_branching_and_risk_bands_are_extracted(self) -> None:
        source = """
Create a questionnaire artifact for screening burnout risk in working adults.

Use adaptive branching. The next question must depend on the previous answer.

Questions:
1. How often do you feel emotionally exhausted after work?
- Rarely — 0 points -> go to question 3
- Sometimes — 1 point -> go to question 2
- Often — 2 points -> go to question 2

2. When exhaustion is present, does rest usually restore your energy by the next day?
- Yes — 0 points -> go to question 3
- Partly — 1 point -> go to question 3
- No — 2 points -> go to question 3

Risk bands:
- 0–2 -> low burnout risk
- 3–5 -> moderate burnout risk
- 6+ -> high burnout risk
""".strip()
        operation = EditOperation(intent_type="replace_questions_from_text", target_section="questions", requires_compilation=True)
        spec = asyncio.run(compile_questionnaire_spec(source, default_draft(), operation, "en"))
        self.assertEqual(spec.artifact_type, "questionnaire")
        self.assertEqual(len(spec.risk_bands), 3)
        self.assertEqual(spec.risk_bands[0].label.lower(), "low burnout risk")
        self.assertEqual(spec.risk_bands[-1].label.lower(), "high burnout risk")
        self.assertEqual(spec.questions[0].options[0].next_question_id, "q3")
        self.assertEqual(spec.questions[0].options[1].next_question_id, "q2")

    def test_burnout_sections_do_not_pollute_last_question_options(self) -> None:
        source = """
Create a questionnaire artifact for screening burnout risk in working adults.

Use adaptive branching. The next question must depend on the previous answer.

Questions:
1. How often do you feel emotionally exhausted after work?
- Rarely — 0 points -> go to question 3
- Sometimes — 1 point -> go to question 2
- Often — 2 points -> go to question 2

5. Is your concentration or work effectiveness lower than usual?
- No — 0 points
- Sometimes — 1 point
- Often — 2 points

Scoring:
- sum all option scores that were actually asked

Risk bands:
- 0–2 -> low burnout risk
- 3–5 -> moderate burnout risk
- 6+ -> high burnout risk

Report:
- summarize exhaustion
- summarize detachment
- summarize work impact
- use supportive wording
- do not diagnose depression or anxiety
""".strip()
        operation = EditOperation(intent_type="replace_questions_from_text", target_section="questions", requires_compilation=True)
        spec = asyncio.run(compile_questionnaire_spec(source, default_draft(), operation, "en"))
        self.assertEqual(len(spec.questions[-1].options), 3)
        self.assertEqual(spec.questions[-1].options[-1].label, "Often")
        self.assertGreaterEqual(len(spec.report_requirements), 3)
        self.assertIn("summarize exhaustion", [item.lower() for item in spec.report_requirements])

    def test_burnout_single_prompt_mode_keeps_risk_bands_and_report_requirements(self) -> None:
        source = """
Create a questionnaire artifact for screening burnout risk in working adults.

Use adaptive branching. The next question must depend on the previous answer.

Questions:
1. How often do you feel emotionally exhausted after work?
- Rarely — 0 points -> go to question 3
- Sometimes — 1 point -> go to question 2
- Often — 2 points -> go to question 2

2. When exhaustion is present, does rest usually restore your energy by the next day?
- Yes — 0 points -> go to question 3
- Partly — 1 point -> go to question 3
- No — 2 points -> go to question 3

3. Has your work become more cynical, detached, or emotionally numb recently?
- No — 0 points -> go to question 5
- A little — 1 point -> go to question 4
- Clearly yes — 2 points -> go to question 4

4. Is this affecting your relationships with colleagues, patients, or clients?
- No — 0 points -> go to question 5
- Sometimes — 1 point -> go to question 5
- Often — 2 points -> go to question 5

5. Is your concentration or work effectiveness lower than usual?
- No — 0 points
- Sometimes — 1 point
- Often — 2 points

Scoring:
- sum all option scores that were actually asked

Risk bands:
- 0–2 -> low burnout risk
- 3–5 -> moderate burnout risk
- 6+ -> high burnout risk

Report:
- summarize exhaustion
- summarize detachment
- summarize work impact
- use supportive wording
- do not diagnose depression or anxiety
""".strip()
        operation = EditOperation(intent_type="replace_questions_from_text", target_section="questions", requires_compilation=True, framework="burnout")
        spec = asyncio.run(compile_questionnaire_spec(source, default_draft(), operation, "en"))
        self.assertEqual(spec.artifact_type, "questionnaire")
        self.assertEqual((spec.framework or "").lower(), "burnout")
        self.assertEqual(len(spec.questions), 5)
        self.assertEqual(len(spec.risk_bands), 3)
        self.assertGreaterEqual(len(spec.report_requirements), 3)

    def test_pending_proposal_typo_confirmation_applies(self) -> None:
        pending = {
            "operation": {
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "requires_confirmation": True,
                "framework": None,
                "rationale": None,
                "clarification_question": None,
                "rollback_version_id": None,
            },
            "spec": {
                "artifact_type": "questionnaire",
                "topic": "stress",
                "framework": "burnout",
                "title": None,
                "description": None,
                "target_population": None,
                "questions": [{"id": "q1", "text": "Q1", "question_type": "single_choice", "source": "source", "options": [{"label": "A", "value": "a", "score": 0}, {"label": "B", "value": "b", "score": 1}], "notes": None}],
                "scoring_method": "sum_of_option_scores",
                "risk_bands": [{"min_score": 0, "max_score": 2, "label": "low"}],
                "anamnesis_sections": [],
                "red_flags": [],
                "assessment_output": None,
                "diagnostic_inputs": [],
                "rule_nodes": [],
                "conclusion_template": None,
                "source_excerpt": "source",
            },
            "review": {
                "is_valid": True,
                "severity": "info",
                "findings": [],
                "missing_information": [],
                "proposed_repairs": [],
                "should_block_apply": False,
            },
            "source_message": "source",
        }
        routed = asyncio.run(route_specialist_message({"language": "ru", "user_message": "подвержить", "pending_proposal": pending}))
        self.assertEqual(routed["next_action"], "APPLY_PENDING_PROPOSAL")

    def test_review_help_request_explains_next_step(self) -> None:
        pending = {
            "operation": {
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "requires_confirmation": True,
                "framework": "burnout",
                "rationale": None,
                "clarification_question": None,
                "rollback_version_id": None,
            },
            "spec": {
                "artifact_type": "questionnaire",
                "topic": "stress",
                "framework": "burnout",
                "title": None,
                "description": None,
                "target_population": None,
                "questions": [{"id": "q1", "text": "Q1", "question_type": "single_choice", "source": "source", "options": [{"label": "A", "value": "a", "score": 0}, {"label": "B", "value": "b", "score": 1}], "notes": None}],
                "scoring_method": "sum_of_option_scores",
                "risk_bands": [],
                "anamnesis_sections": [],
                "red_flags": [],
                "assessment_output": None,
                "diagnostic_inputs": [],
                "rule_nodes": [],
                "conclusion_template": None,
                "source_excerpt": "source",
            },
            "review": {
                "is_valid": False,
                "severity": "error",
                "findings": [{"severity": "error", "message": "No risk bands were extracted from the specialist source text.", "field_path": "risk_bands"}],
                "missing_information": ["Risk bands are missing for sum_of_option_scores."],
                "proposed_repairs": [],
                "should_block_apply": True,
            },
            "source_message": "source",
        }
        result = asyncio.run(
            discuss_specialist_goal(
                {
                    "language": "ru",
                    "draft": default_draft(),
                    "pending_proposal": pending,
                    "user_message": "как решить эти проблемы? помоги мне",
                    "analyst_decision": {"next_action": "DISCUSS"},
                }
            )
        )
        self.assertIn("Результат проверки", result["assistant_reply"])
        self.assertIn("risk bands", result["assistant_reply"])
        self.assertIn("примени предложение", result["assistant_reply"])

    def test_risk_band_followup_uses_pending_questions_as_base(self) -> None:
        pending = {
            "operation": {
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "requires_confirmation": True,
                "framework": "burnout",
                "rationale": None,
                "clarification_question": None,
                "rollback_version_id": None,
            },
            "spec": {
                "artifact_type": "questionnaire",
                "topic": "stress",
                "framework": "burnout",
                "title": None,
                "description": None,
                "target_population": None,
                "questions": [
                    {"id": "q1", "text": "How often do you feel emotionally exhausted after work?", "question_type": "single_choice", "source": "source", "options": [{"label": "Rarely", "value": "rarely", "score": 0}, {"label": "Often", "value": "often", "score": 2}], "notes": None},
                    {"id": "q2", "text": "Is your concentration or work effectiveness lower than usual?", "question_type": "single_choice", "source": "source", "options": [{"label": "No", "value": "no", "score": 0}, {"label": "Often", "value": "often", "score": 2}], "notes": None},
                ],
                "scoring_method": "sum_of_option_scores",
                "risk_bands": [],
                "report_requirements": [],
                "anamnesis_sections": [],
                "red_flags": [],
                "assessment_output": None,
                "diagnostic_inputs": [],
                "rule_nodes": [],
                "conclusion_template": None,
                "source_excerpt": "source",
            },
            "review": {
                "is_valid": True,
                "severity": "info",
                "findings": [],
                "missing_information": ["Risk bands are missing for sum_of_option_scores."],
                "proposed_repairs": [],
                "should_block_apply": False,
            },
            "source_message": "source",
        }
        result = asyncio.run(
            update_draft(
                {
                    "language": "en",
                    "draft": default_draft(),
                    "pending_proposal": pending,
                    "user_message": "Add burnout risk bands for this questionnaire.\n\nScoring:\n- sum all option scores that were actually asked\n\nRisk bands:\n- 0–2 -> low burnout risk\n- 3–5 -> moderate burnout risk\n- 6+ -> high burnout risk",
                }
            )
        )
        self.assertEqual(result["pending_proposal"]["spec"]["framework"], "burnout")
        self.assertEqual(len(result["pending_proposal"]["spec"]["questions"]), 2)
        self.assertEqual(len(result["pending_proposal"]["spec"]["risk_bands"]), 3)

    def test_direct_compile_and_publish_commands_route_without_analyst(self) -> None:
        routed_compile = asyncio.run(route_specialist_message({"language": "en", "user_message": "compile"}))
        routed_publish = asyncio.run(route_specialist_message({"language": "en", "user_message": "publish"}))
        routed_help = asyncio.run(route_specialist_message({"language": "ru", "user_message": "какие графы есть?"}))
        self.assertEqual(routed_compile["next_action"], "COMPILE")
        self.assertEqual(routed_publish["next_action"], "PUBLISH")
        self.assertEqual(routed_help["next_action"], "SHOW_HELP")

    def test_build_material_shortcut_forces_proposal_even_with_existing_draft(self) -> None:
        draft = {
            "understood": {"topic": "stress", "artifact_type": "questionnaire", "framework": "burnout"},
            "candidate_questions": [],
            "candidate_scoring_rules": {},
            "candidate_risk_bands": [],
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        message = """
Questions:
1. How often do you feel emotionally exhausted after work?
- Rarely — 0 points -> go to question 3
- Sometimes — 1 point -> go to question 2
""".strip()
        routed = asyncio.run(route_specialist_message({"language": "en", "draft": draft, "user_message": message}))
        self.assertEqual(routed["next_action"], "DISCUSS")
        self.assertTrue(routed["analyst_decision"]["should_prepare_proposal"])

    def test_findrisk_questionnaire_is_not_retyped_as_rule_graph(self) -> None:
        source = """
я хочу собрать финдриск для диабета

1. Возраст
- <45 лет — 0 баллов
- 45–54 лет — 2 балла
- 55–64 лет — 3 балла
- >64 лет — 4 балла
""".strip()
        operation = EditOperation(intent_type="replace_questions_from_text", target_section="questions", requires_compilation=True, framework="findrisk")
        spec = asyncio.run(compile_questionnaire_spec(source, default_draft(), operation, "ru"))
        self.assertEqual(spec.artifact_type, "questionnaire")
        self.assertEqual((spec.framework or "").lower(), "findrisk")
        self.assertEqual(spec.scoring_method, "sum_of_option_scores")

    def test_findrisk_message_normalizes_edit_operation_to_questions(self) -> None:
        source = """
я хочу собрать FINDRISC для скрининга риска развития диабета 2 типа у взрослых. Это questionnaire, не clinical rule graph.

1. Возраст
- <45 лет — 0 баллов
- 45–54 лет — 2 балла
""".strip()
        op = asyncio.run(plan_edit_operation(source, default_draft(), "ru", False))
        self.assertEqual(op.intent_type, "replace_questions_from_text")
        self.assertEqual(op.target_section, "questions")
        self.assertTrue(op.requires_compilation)

    def test_full_diabetes_prompt_infers_findrisk_and_risk_bands(self) -> None:
        source = """
Create a questionnaire artifact for screening type 2 diabetes risk in adults.

Questions:
1. Age
- <45 years — 0 points
- 45–54 years — 2 points
- 55–64 years — 3 points
- >64 years — 4 points

2. Body mass index
- <25 kg/m² — 0 points
- 25–30 kg/m² — 1 point
- >30 kg/m² — 3 points

3. Waist circumference
- <94 cm — 0 points
- 94–102 cm — 3 points
- >102 cm — 4 points

4. Daily physical activity
- Yes — 0 points
- No — 2 points

5. Vegetables, fruit, or berries every day
- Yes — 0 points
- No — 2 points

6. Antihypertensive medication
- No — 0 points
- Yes — 2 points

7. Previously elevated blood glucose
- No — 0 points
- Yes — 2 points

8. Family history of diabetes
- No — 0 points
- Extended family — 3 points
- First-degree relative — 5 points
""".strip()
        operation = EditOperation(intent_type="replace_questions_from_text", target_section="questions", requires_compilation=True)
        spec = asyncio.run(compile_questionnaire_spec(source, default_draft(), operation, "en"))
        self.assertEqual(spec.artifact_type, "questionnaire")
        self.assertEqual((spec.framework or "").lower(), "findrisk")
        self.assertEqual(spec.scoring_method, "sum_of_option_scores")
        self.assertGreaterEqual(len(spec.risk_bands), 3)

    def test_findrisk_apply_hydrates_risk_bands_from_questions_only_proposal(self) -> None:
        pending = {
            "operation": {
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "requires_confirmation": True,
                "framework": None,
                "rationale": None,
                "clarification_question": None,
                "rollback_version_id": None,
            },
            "spec": {
                "artifact_type": "questionnaire",
                "topic": "diabetes",
                "framework": None,
                "title": None,
                "description": None,
                "target_population": "adults",
                "questions": [
                    {"id": "q1", "text": "Age", "question_type": "single_choice", "source": "source", "options": [{"label": "<45 years", "value": "opt_1", "score": 0}], "notes": None},
                    {"id": "q2", "text": "Body mass index", "question_type": "single_choice", "source": "source", "options": [{"label": "<25 kg/m²", "value": "opt_1", "score": 0}], "notes": None},
                    {"id": "q3", "text": "Waist circumference", "question_type": "single_choice", "source": "source", "options": [{"label": "<94 cm", "value": "opt_1", "score": 0}], "notes": None},
                    {"id": "q4", "text": "Daily physical activity", "question_type": "single_choice", "source": "source", "options": [{"label": "Yes", "value": "opt_1", "score": 0}], "notes": None},
                    {"id": "q5", "text": "Vegetables, fruit, or berries every day", "question_type": "single_choice", "source": "source", "options": [{"label": "Yes", "value": "opt_1", "score": 0}], "notes": None},
                    {"id": "q6", "text": "Antihypertensive medication", "question_type": "single_choice", "source": "source", "options": [{"label": "No", "value": "opt_1", "score": 0}], "notes": None},
                    {"id": "q7", "text": "Previously elevated blood glucose", "question_type": "single_choice", "source": "source", "options": [{"label": "No", "value": "opt_1", "score": 0}], "notes": None},
                    {"id": "q8", "text": "Family history of diabetes", "question_type": "single_choice", "source": "source", "options": [{"label": "No", "value": "opt_1", "score": 0}], "notes": None},
                ],
                "scoring_method": "sum_of_option_scores",
                "risk_bands": [],
                "anamnesis_sections": [],
                "red_flags": [],
                "assessment_output": None,
                "diagnostic_inputs": [],
                "rule_nodes": [],
                "conclusion_template": None,
                "source_excerpt": "source",
            },
            "review": {
                "is_valid": True,
                "severity": "info",
                "findings": [],
                "missing_information": [],
                "proposed_repairs": [],
                "should_block_apply": False,
            },
            "source_message": "source",
        }
        result = asyncio.run(
            apply_pending_proposal(
                {
                    "language": "en",
                    "conversation_id": "findrisk_full_prompt",
                    "draft": default_draft(),
                    "pending_proposal": pending,
                }
            )
        )
        self.assertEqual(result["draft"]["understood"]["framework"], "findrisk")
        self.assertGreaterEqual(len(result["draft"]["candidate_risk_bands"]), 3)

    def test_replace_risk_bands_operation_gets_required_flags(self) -> None:
        source = """
добавь оценку рисков по сумме баллов для этого questionnaire FINDRISC.

Интерпретация суммы баллов:
- <7 — низкий риск, вероятность 1%
- 7–11 — слегка повышен, вероятность 4%
""".strip()
        draft = {
            "understood": {"topic": "diabetes", "artifact_type": "clinical_rule_graph"},
            "candidate_questions": [{"id": "q1", "text": "Возраст", "question_type": "single_choice", "options": [{"label": "<45", "value": "1", "score": 0}], "source": "starter"}],
            "candidate_scoring_rules": {},
            "candidate_risk_bands": [],
            "candidate_anamnesis_sections": [],
            "candidate_red_flags": [],
            "candidate_assessment_output": None,
            "candidate_diagnostic_inputs": ["Возраст"],
            "candidate_rule_nodes": [{"id": "rule_1", "label": "Возраст", "condition": "Возраст", "conditions_ast": [{"field": "Возраст", "operator": "present", "value": ""}], "outcome": "Возраст"}],
            "candidate_conclusion_template": None,
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        op = asyncio.run(plan_edit_operation(source, draft, "ru", False))
        self.assertEqual(op.intent_type, "replace_risk_bands")
        self.assertEqual(op.target_section, "risk_bands")
        self.assertTrue(op.requires_compilation)

    def test_end_to_end_versioning_diff_and_rollback(self) -> None:
        base_draft = default_draft()
        pending = {
            "operation": {
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "requires_confirmation": True,
                "framework": None,
                "rationale": None,
                "clarification_question": None,
                "rollback_version_id": None,
            },
            "spec": {
                "artifact_type": "questionnaire",
                "topic": "diabetes",
                "framework": "findrisk",
                "title": None,
                "description": "findrisk draft",
                "target_population": "adults",
                "questions": [{"id": "q1", "text": "Возраст", "question_type": "single_choice", "source": "source text", "options": [{"label": "<45", "value": "opt_1", "score": 0}], "notes": None}],
                "scoring_method": "sum_of_option_scores",
                "risk_bands": [{"min_score": 0, "max_score": 6, "label": "Low", "meaning": "low"}],
                "anamnesis_sections": [],
                "red_flags": [],
                "assessment_output": None,
                "diagnostic_inputs": [],
                "rule_nodes": [],
                "conclusion_template": None,
                "source_excerpt": "source",
            },
            "review": {
                "is_valid": True,
                "severity": "info",
                "findings": [],
                "missing_information": [],
                "proposed_repairs": [],
                "should_block_apply": False,
            },
            "source_message": "source",
        }
        applied = asyncio.run(
            apply_pending_proposal(
                {
                    "language": "ru",
                    "conversation_id": "e2e_versions",
                    "draft": base_draft,
                    "pending_proposal": pending,
                }
            )
        )
        self.assertIn("версию v", applied["assistant_reply"])

        diff = asyncio.run(show_diff({"language": "ru", "draft": applied["draft"], "pending_proposal": pending}))
        self.assertIn("Планируемые изменения", diff["assistant_reply"])

        versions = asyncio.run(show_versions({"language": "ru", "conversation_id": "e2e_versions"}))
        self.assertIn("Последние версии draft", versions["assistant_reply"])

        old_version_id = save_specialist_draft_version("e2e_versions", default_draft(), note="seed rollback")
        rolled = asyncio.run(
            rollback_draft(
                {
                    "language": "ru",
                    "conversation_id": "e2e_versions",
                    "edit_operation": {"intent_type": "rollback_draft", "rollback_version_id": old_version_id},
                }
            )
        )
        self.assertIn("Откатил draft", rolled["assistant_reply"])

    def test_publish_is_blocked_when_review_has_findings(self) -> None:
        draft = {
            "understood": {"topic": "diabetes", "artifact_type": "questionnaire"},
            "candidate_questions": [{"id": "q1", "text": "Возраст", "question_type": "single_choice", "options": [{"label": "<45", "value": "opt_1", "score": 0}, {"label": "45-54", "value": "opt_2", "score": 2}], "source": "source text"}],
            "candidate_scoring_rules": {"method": "sum_of_option_scores"},
            "candidate_risk_bands": [{"min_score": 0, "max_score": 6, "label": "Low"}],
            "candidate_anamnesis_sections": [],
            "candidate_red_flags": [],
            "candidate_assessment_output": None,
            "candidate_diagnostic_inputs": [],
            "candidate_rule_nodes": [],
            "candidate_conclusion_template": None,
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        compiled = asyncio.run(compile_draft({"language": "ru", "conversation_id": "publish_gate", "draft": draft, "critic_review": {}}))
        blocked = asyncio.run(
            publish_draft(
                {
                    "language": "ru",
                    "conversation_id": "publish_gate",
                    "draft": draft,
                    "compile_result": compiled["compile_result"],
                    "critic_review": {
                        "is_valid": True,
                        "severity": "warning",
                        "findings": [{"severity": "warning", "message": "Needs manual review"}],
                        "missing_information": [],
                        "proposed_repairs": [],
                        "should_block_apply": False,
                    },
                }
            )
        )
        self.assertIn("Публикация заблокирована", blocked["assistant_reply"])

    def test_questionnaire_preview_suggests_add_risk_bands(self) -> None:
        draft = {
            "understood": {"topic": "diabetes", "artifact_type": "questionnaire"},
            "candidate_questions": [{"id": "q1", "text": "Возраст", "question_type": "single_choice", "options": [{"label": "<45", "value": "opt_1", "score": 0}], "source": "source text"}],
            "candidate_scoring_rules": {"method": "sum_of_option_scores"},
            "candidate_risk_bands": [],
            "candidate_anamnesis_sections": [],
            "candidate_red_flags": [],
            "candidate_assessment_output": None,
            "candidate_diagnostic_inputs": [],
            "candidate_rule_nodes": [],
            "candidate_conclusion_template": None,
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        preview = asyncio.run(show_preview({"language": "ru", "draft": draft}))
        self.assertIn("не хватает risk bands", preview["assistant_reply"])

    def test_compile_reply_suggests_publish(self) -> None:
        draft = {
            "understood": {"topic": "diabetes", "artifact_type": "questionnaire"},
            "candidate_questions": [{"id": "q1", "text": "Возраст", "question_type": "single_choice", "options": [{"label": "<45", "value": "opt_1", "score": 0}, {"label": "45-54", "value": "opt_2", "score": 2}], "source": "source text"}],
            "candidate_scoring_rules": {"method": "sum_of_option_scores"},
            "candidate_risk_bands": [{"min_score": 0, "max_score": 6, "label": "Low"}],
            "candidate_anamnesis_sections": [],
            "candidate_red_flags": [],
            "candidate_assessment_output": None,
            "candidate_diagnostic_inputs": [],
            "candidate_rule_nodes": [],
            "candidate_conclusion_template": None,
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        compiled = asyncio.run(compile_draft({"language": "ru", "conversation_id": "compile_hint", "draft": draft}))
        self.assertIn("`publish`", compiled["assistant_reply"])

    def test_selective_apply_risks_only_keeps_existing_questions(self) -> None:
        draft = {
            "understood": {"topic": "diabetes", "artifact_type": "questionnaire"},
            "candidate_questions": [{"id": "q1", "text": "Возраст", "question_type": "single_choice", "options": [{"label": "<45", "value": "opt_1", "score": 0}], "source": "existing"}],
            "candidate_scoring_rules": {"method": "sum_of_option_scores"},
            "candidate_risk_bands": [],
            "candidate_anamnesis_sections": [],
            "candidate_red_flags": [],
            "candidate_assessment_output": None,
            "candidate_diagnostic_inputs": [],
            "candidate_rule_nodes": [],
            "candidate_conclusion_template": None,
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        pending = {
            "operation": {
                "intent_type": "replace_questions_from_text",
                "target_section": "questions",
                "requires_compilation": True,
                "requires_confirmation": True,
                "framework": None,
                "rationale": None,
                "clarification_question": None,
                "rollback_version_id": None,
            },
            "spec": {
                "artifact_type": "questionnaire",
                "topic": "diabetes",
                "framework": None,
                "title": None,
                "description": "findrisk draft",
                "target_population": None,
                "questions": [{"id": "q2", "text": "ИМТ", "question_type": "single_choice", "source": "proposal", "source_excerpt": "2. Индекс массы тела", "source_line_range": "5-8", "options": [{"label": "<25", "value": "opt_1", "score": 0}], "notes": None}],
                "scoring_method": "sum_of_option_scores",
                "risk_bands": [{"min_score": 0, "max_score": 6, "label": "Low", "meaning": "low", "source_excerpt": "- <7 — низкий риск"}],
                "anamnesis_sections": [],
                "red_flags": [],
                "assessment_output": None,
                "diagnostic_inputs": [],
                "rule_nodes": [],
                "conclusion_template": None,
                "source_excerpt": "risk update",
            },
            "review": {"is_valid": True, "severity": "info", "findings": [], "missing_information": [], "proposed_repairs": [], "should_block_apply": False},
            "source_message": "risk update",
        }
        result = asyncio.run(
            apply_pending_proposal(
                {
                    "language": "ru",
                    "conversation_id": "selective_apply",
                    "draft": draft,
                    "pending_proposal": pending,
                    "edit_operation": {"intent_type": "apply_risks_only", "target_section": "risk_bands", "requires_confirmation": False},
                }
            )
        )
        self.assertEqual(len(result["draft"]["candidate_questions"]), 1)
        self.assertEqual(result["draft"]["candidate_questions"][0]["text"], "Возраст")
        self.assertEqual(len(result["draft"]["candidate_risk_bands"]), 1)

    def test_detailed_draft_shows_source_excerpt(self) -> None:
        draft = {
            "understood": {"topic": "diabetes", "description": "topic", "framework": "findrisk"},
            "candidate_questions": [{"id": "q1", "text": "Возраст", "source": "starter FINDRISC-like scaffold", "source_excerpt": "1. Возраст", "source_line_range": "1-4", "options": []}],
            "candidate_scoring_rules": {"method": "sum_of_option_scores"},
            "candidate_risk_bands": [{"min_score": 0, "max_score": 1, "label": "Low", "source_excerpt": "- <7 — низкий риск"}],
            "candidate_report_requirements": [],
            "candidate_safety_requirements": [],
            "missing_fields": [],
        }
        result = asyncio.run(show_detailed_draft({"language": "ru", "draft": draft}))
        self.assertIn("excerpt: 1. Возраст", result["assistant_reply"])
        self.assertIn("lines: 1-4", result["assistant_reply"])


if __name__ == "__main__":
    unittest.main()
