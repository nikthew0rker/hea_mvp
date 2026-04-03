from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hea.shared.runtime import apply_answer, build_report_payload, create_assessment_state, get_current_question, normalize_answer, render_report_html, render_report_pdf  # noqa: E402


class NormalizeAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.question = {
            "id": "q1",
            "text": "Pick one",
            "options": [
                {"label": "Yes", "value": "yes", "score": 1},
                {"label": "No", "value": "no", "score": 0},
            ],
        }

    def test_matches_option_number(self) -> None:
        result = normalize_answer(self.question, "1")
        self.assertEqual(result["status"], "full_match")
        self.assertEqual(result["value"], "yes")

    def test_matches_exact_label(self) -> None:
        result = normalize_answer(self.question, "Yes")
        self.assertEqual(result["status"], "full_match")
        self.assertEqual(result["value"], "yes")

    def test_matches_alias_word(self) -> None:
        result = normalize_answer(self.question, "ok")
        self.assertEqual(result["status"], "full_match")
        self.assertEqual(result["value"], "yes")

    def test_rejects_partial_substring(self) -> None:
        result = normalize_answer(self.question, "es")
        self.assertEqual(result["status"], "no_match")

    def test_clinical_rule_graph_synthesizes_runtime_questions_and_matches_rule(self) -> None:
        graph = {
            "title": "Diabetes Rule Graph",
            "artifact_type": "clinical_rule_graph",
            "questions": [],
            "diagnostic_inputs": ["Глюкоза натощак"],
            "rule_nodes": [
                {
                    "id": "rule_1",
                    "label": "Высокий риск",
                    "condition": "Глюкоза натощак >= 7.0",
                    "conditions_ast": [{"field": "Глюкоза натощак", "operator": ">=", "value": "7.0"}],
                    "outcome": "Высокий риск диабета",
                }
            ],
        }
        state = create_assessment_state(graph, "ru")
        question = get_current_question(graph, state)
        self.assertEqual(question["text"], "Глюкоза натощак")

        normalized = normalize_answer(question, "7.2")
        result = apply_answer(graph, state, normalized)
        self.assertTrue(result["completed"])
        self.assertEqual(result["assessment_state"]["result"]["risk_band"]["label"], "Высокий риск")

    def test_branching_questionnaire_skips_followup_by_option(self) -> None:
        graph = {
            "title": "Burnout Demo",
            "artifact_type": "questionnaire",
            "questions": [
                {
                    "id": "q1",
                    "text": "How often do you feel emotionally exhausted after work?",
                    "question_type": "single_choice",
                    "options": [
                        {"label": "Rarely", "value": "rarely", "score": 0, "next_question_id": "q3"},
                        {"label": "Often", "value": "often", "score": 2, "next_question_id": "q2"},
                    ],
                },
                {
                    "id": "q2",
                    "text": "Does rest restore your energy by the next day?",
                    "question_type": "single_choice",
                    "options": [
                        {"label": "Yes", "value": "yes", "score": 0},
                        {"label": "No", "value": "no", "score": 2},
                    ],
                },
                {
                    "id": "q3",
                    "text": "Is your concentration lower than usual?",
                    "question_type": "single_choice",
                    "options": [
                        {"label": "No", "value": "no", "score": 0},
                        {"label": "Yes", "value": "yes", "score": 1},
                    ],
                },
            ],
            "risk_bands": [{"min_score": 0, "max_score": 10, "label": "Low burnout risk", "meaning": "Demo"}],
            "scoring": {"method": "sum_of_option_scores"},
        }
        state = create_assessment_state(graph, "en")
        normalized = normalize_answer(graph["questions"][0], "1")
        result = apply_answer(graph, state, normalized)
        self.assertFalse(result["completed"])
        self.assertEqual(result["assessment_state"]["question_index"], 2)
        self.assertIn("Question 3/3", result["reply_text"])

    def test_render_report_html_contains_key_fields(self) -> None:
        html = render_report_html(
            {
                "graph_title": "Diabetes",
                "score_total": 7,
                "risk_band": {"label": "Elevated risk", "meaning": "Some risk markers are present."},
                "_graph": {"topic": "diabetes", "report_rules": []},
                "_answers": [],
            },
            "en",
        )
        self.assertIn("<html>", html)
        self.assertIn("Diabetes", html)
        self.assertIn("Elevated risk", html)
        self.assertIn("Next steps", html)

    def test_build_report_payload_uses_report_rules_for_burnout_summary(self) -> None:
        payload = build_report_payload(
            {
                "graph_title": "Stress",
                "score_total": 3,
                "risk_band": {"label": "moderate burnout risk", "meaning": "Moderate burnout risk"},
            },
            {
                "topic": "stress",
                "report_rules": [
                    "summarize exhaustion",
                    "summarize detachment",
                    "summarize work impact",
                    "use supportive wording",
                    "do not diagnose depression or anxiety",
                ],
            },
            [
                {"question_text": "How often do you feel emotionally exhausted after work?", "selected_option": "Sometimes"},
                {"question_text": "Has your work become more cynical, detached, or emotionally numb recently?", "selected_option": "A little"},
                {"question_text": "Is your concentration or work effectiveness lower than usual?", "selected_option": "Often"},
            ],
            "en",
        )
        self.assertTrue(payload["summaries"])
        self.assertTrue(payload["recommendations"])
        self.assertIn("Exhaustion:", payload["summaries"][0])

    def test_render_report_pdf_returns_pdf_bytes(self) -> None:
        pdf = render_report_pdf(
            {
                "graph_title": "Burnout",
                "score_total": 3,
                "risk_band": {"label": "Moderate burnout risk", "meaning": "Some signs are present."},
                "_graph": {"topic": "stress", "report_rules": ["burnout", "summarize exhaustion"]},
                "_answers": [{"question_text": "How often do you feel emotionally exhausted after work?", "selected_option": "Sometimes"}],
            },
            "en",
        )
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))


if __name__ == "__main__":
    unittest.main()
