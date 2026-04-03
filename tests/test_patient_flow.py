from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hea.graphs.patient.nodes import (  # noqa: E402
    red_flag_guidance,
    reset_to_free,
    restate_consent,
    route_user_message,
    search_assessments,
    select_candidate,
    show_last_report,
    show_post_options,
)
from hea.graphs.patient.graph import build_patient_graph  # noqa: E402
from hea.services.patient_controller.app import app as patient_app, report as patient_report, report_pdf as patient_report_pdf  # noqa: E402
from hea.shared.db import init_db  # noqa: E402
from hea.shared.patient_pipeline import extract_patient_intake  # noqa: E402
from hea.shared.registry import upsert_graph  # noqa: E402
from hea.shared.search import search_graphs  # noqa: E402
from hea.shared.session_store import save_patient_session  # noqa: E402


class PatientFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        init_db()
        upsert_graph(
            {
                "graph_id": "diabetes_a",
                "title": "Diabetes Risk A",
                "topic": "diabetes",
                "description": "Adult diabetes risk screening",
                "tags": ["diabetes"],
                "entry_signals": ["diabetes risk"],
                "questions": [{"id": "q1", "text": "Возраст", "options": []}],
                "risk_bands": [],
                "scoring": {},
                "report_rules": [],
                "safety_rules": [],
            }
        )
        upsert_graph(
            {
                "graph_id": "diabetes_b",
                "title": "Diabetes Risk B",
                "topic": "diabetes",
                "description": "Alternative adult diabetes screening",
                "tags": ["diabetes"],
                "entry_signals": ["diabetes screening"],
                "questions": [{"id": "q1", "text": "Возраст", "options": []}],
                "risk_bands": [],
                "scoring": {},
                "report_rules": [],
                "safety_rules": [],
            }
        )
        upsert_graph(
            {
                "graph_id": "sleep_c",
                "title": "Sleep Assessment",
                "topic": "sleep",
                "description": "Sleep quality screening",
                "tags": ["sleep"],
                "entry_signals": ["insomnia"],
                "questions": [{"id": "q1", "text": "Sleep quality", "options": []}],
                "risk_bands": [],
                "scoring": {},
                "report_rules": [],
                "safety_rules": [],
            }
        )

    def test_red_flag_message_routes_to_guidance(self) -> None:
        routed = asyncio.run(route_user_message({"user_message": "У меня боль в груди и тяжело дышать", "mode": "free_conversation"}))
        self.assertEqual(routed["next_action"], "RED_FLAG_GUIDANCE")
        guidance = asyncio.run(red_flag_guidance({"language": "ru", "red_flag_status": routed["red_flag_status"]}))
        self.assertIn("неотложной", guidance["assistant_reply"])

    def test_search_can_request_disambiguation(self) -> None:
        result = asyncio.run(search_assessments({"language": "ru", "user_message": "diabetes"}))
        self.assertEqual(result["mode"], "awaiting_selection")
        self.assertIn("Выберите номер", result["assistant_reply"])
        self.assertIn("Причина выбора:", result["assistant_reply"])

    def test_select_candidate_moves_to_consent(self) -> None:
        search_result = asyncio.run(search_assessments({"language": "ru", "user_message": "diabetes"}))
        selected = asyncio.run(
            select_candidate(
                {
                    "language": "ru",
                    "candidates": search_result["candidates"],
                    "analyst_decision": {"selected_candidate_index": 1},
                }
            )
        )
        self.assertEqual(selected["mode"], "awaiting_consent")
        self.assertIn("Хотите пройти его сейчас", selected["assistant_reply"])

    def test_patient_routing_preserves_symptom_summary(self) -> None:
        routed = asyncio.run(route_user_message({"user_message": "у меня диабет и высокое давление уже 3 дня", "mode": "free_conversation"}))
        self.assertIn("symptom_summary", routed)
        self.assertTrue(routed["symptom_summary"])
        self.assertIn("symptom_intake", routed)
        self.assertIn("diabetes", routed["symptom_intake"]["suspected_topics"])

    def test_ambiguous_consent_turn_restates_current_selection(self) -> None:
        routed = asyncio.run(route_user_message({"user_message": "не понял", "mode": "awaiting_consent", "selected_graph": {"title": "Diabetes Risk A"}}))
        self.assertEqual(routed["next_action"], "RESTATE_CONSENT")
        reply = asyncio.run(restate_consent({"language": "ru", "selected_graph": {"title": "Diabetes Risk A"}}))
        self.assertIn("ответьте `да`", reply["assistant_reply"])

    def test_ambiguous_post_assessment_turn_keeps_post_context(self) -> None:
        routed = asyncio.run(route_user_message({"user_message": "хмм", "mode": "post_assessment"}))
        self.assertEqual(routed["next_action"], "SHOW_POST_OPTIONS")

    def test_post_assessment_new_request_resets_to_free(self) -> None:
        routed = asyncio.run(route_user_message({"language": "ru", "user_message": "давай новый запрос", "mode": "post_assessment"}))
        self.assertEqual(routed["next_action"], "RESET_TO_FREE")

    def test_reset_to_free_clears_previous_assessment_context(self) -> None:
        reset = asyncio.run(
            reset_to_free(
                {
                    "language": "ru",
                    "mode": "post_assessment",
                    "selected_graph_id": "stress_graph",
                    "selected_graph": {"title": "Stress"},
                    "discovered_graphs": ["stress_graph"],
                    "consent_status": "accepted",
                    "assessment_state": {"status": "completed"},
                    "last_result": {"graph_title": "Stress"},
                    "candidates": [{"graph_id": "stress_graph"}],
                    "red_flag_status": "none",
                    "symptom_summary": "стресс",
                    "last_search_query": "стресс",
                    "symptom_intake": {"symptoms": ["stress"]},
                }
            )
        )
        self.assertEqual(reset["mode"], "free_conversation")
        self.assertIsNone(reset["selected_graph_id"])
        self.assertIsNone(reset["selected_graph"])
        self.assertIsNone(reset["last_result"])
        self.assertIsNone(reset["assessment_state"])
        self.assertIsNone(reset["symptom_intake"])
        self.assertEqual(reset["candidates"], [])

    def test_post_assessment_pdf_request_routes_to_last_report(self) -> None:
        routed = asyncio.run(route_user_message({"language": "ru", "user_message": "пдф?", "mode": "post_assessment"}))
        self.assertEqual(routed["next_action"], "SHOW_LAST_REPORT")

    def test_post_assessment_typo_explain_routes_correctly(self) -> None:
        routed = asyncio.run(route_user_message({"language": "ru", "user_message": "обьясни", "mode": "post_assessment"}))
        self.assertEqual(routed["next_action"], "EXPLAIN_LAST_RESULT")
        reply = asyncio.run(show_post_options({"language": "ru"}))
        self.assertIn("последний результат", reply["assistant_reply"])

    def test_patient_intake_accumulates_symptoms_and_duration(self) -> None:
        first = extract_patient_intake("у меня диабет и высокое давление", None)
        second = extract_patient_intake("это уже 3 дня и боль усиливается", first.model_dump(mode="json"))
        self.assertIn("diabetes", second.suspected_topics)
        self.assertTrue(second.duration)
        self.assertEqual(second.severity, "severe")

    def test_patient_intake_understands_blood_sugar_as_diabetes_signal(self) -> None:
        intake = extract_patient_intake("меня беспокоит уровень сахара в крови", None)
        self.assertIn("diabetes", intake.suspected_topics)
        self.assertTrue(any(symptom in intake.symptoms for symptom in ["сахар", "сахар в крови"]))

    def test_model_red_flag_false_positive_is_sanitized(self) -> None:
        routed = asyncio.run(route_user_message({"user_message": "меня беспокоит уровень сахара в крови", "mode": "free_conversation"}))
        self.assertEqual(routed["next_action"], "SEARCH")
        self.assertEqual(routed["red_flag_status"], "none")

    def test_patient_language_follows_current_user_turn(self) -> None:
        routed = asyncio.run(route_user_message({"language": "ru", "user_message": "yes", "mode": "awaiting_consent"}))
        self.assertEqual(routed["language"], "en")

    def test_search_reply_uses_intake_context(self) -> None:
        result = asyncio.run(
            search_assessments(
                {
                    "language": "ru",
                    "user_message": "диабет",
                    "symptom_summary": "keywords=диабет, давление",
                    "symptom_intake": {
                        "summary": "keywords=диабет, давление",
                        "symptoms": ["давление"],
                        "suspected_topics": ["diabetes"],
                        "duration": "3 дня",
                        "severity": "moderate",
                        "free_text": "диабет и давление",
                    },
                }
            )
        )
        self.assertIn("Контекст:", result["assistant_reply"])
        self.assertNotIn("overlap=", result["assistant_reply"])

    def test_intake_topics_improve_ranking(self) -> None:
        results = search_graphs(
            "давление",
            top_k=3,
            extra_context="keywords=диабет, давление",
            intake={
                "summary": "keywords=диабет, давление",
                "symptoms": ["давление"],
                "suspected_topics": ["diabetes"],
                "duration": "3 дня",
                "severity": "moderate",
            },
        )
        self.assertTrue(results)
        self.assertEqual(results[0]["metadata"]["topic"], "diabetes")
        self.assertIn("intake_topic=diabetes", results[0]["reason"])

    def test_blood_sugar_query_matches_diabetes_graph(self) -> None:
        results = search_graphs(
            "меня беспокоит уровень сахара в крови",
            top_k=3,
            extra_context="сахар в крови diabetes",
            intake={
                "summary": "keywords=сахар, diabetes",
                "symptoms": ["сахар", "сахар в крови"],
                "suspected_topics": ["diabetes"],
                "duration": None,
                "severity": "unknown",
            },
        )
        self.assertTrue(results)
        self.assertEqual(results[0]["metadata"]["topic"], "diabetes")

    def test_english_sugar_query_matches_diabetes_graph(self) -> None:
        results = search_graphs(
            "i have problem with sugar",
            top_k=3,
            extra_context="sugar diabetes",
            intake={
                "summary": "keywords=sugar, diabetes",
                "symptoms": ["sugar"],
                "suspected_topics": ["diabetes"],
                "duration": None,
                "severity": "unknown",
            },
        )
        self.assertTrue(results)
        self.assertEqual(results[0]["metadata"]["topic"], "diabetes")

    def test_diabet_variant_matches_diabetes_graph(self) -> None:
        results = search_graphs("diabet", top_k=3, extra_context="", intake={})
        self.assertTrue(results)
        self.assertEqual(results[0]["metadata"]["topic"], "diabetes")

    def test_patient_runtime_subgraph_receives_selected_graph(self) -> None:
        app = build_patient_graph().compile()
        state = {
            "conversation_id": "patient_runtime_e2e",
            "language": "ru",
            "mode": "assessment_in_progress",
            "user_message": "1",
            "selected_graph": {
                "graph_id": "diabetes_runtime",
                "title": "Diabetes",
                "artifact_type": "questionnaire",
                "topic": "diabetes",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Возраст",
                        "question_type": "single_choice",
                        "options": [
                            {"label": "<45 лет", "value": "opt_1", "score": 0},
                            {"label": "45–54 лет", "value": "opt_2", "score": 2},
                        ],
                    },
                    {
                        "id": "q2",
                        "text": "ИМТ",
                        "question_type": "single_choice",
                        "options": [
                            {"label": "<25", "value": "opt_1", "score": 0},
                            {"label": ">25", "value": "opt_2", "score": 1},
                        ],
                    },
                ],
                "risk_bands": [{"min_score": 0, "max_score": 10, "label": "Low"}],
            },
            "assessment_state": {
                "status": "in_progress",
                "language": "ru",
                "question_index": 0,
                "answers": [],
                "score_total": 0.0,
                "result": None,
            },
        }
        result = asyncio.run(app.ainvoke(state))
        self.assertEqual(result["assessment_state"]["question_index"], 1)
        self.assertIn("Вопрос 2/2", result["assistant_reply"])

    def test_patient_report_endpoint_returns_html(self) -> None:
        save_patient_session(
            "report_demo",
            {
                "language": "en",
                "last_result": {
                    "graph_title": "Diabetes",
                    "score_total": 7,
                    "risk_band": {"label": "Elevated risk", "meaning": "Some risk markers are present."},
                },
                "selected_graph": {"topic": "diabetes", "report_rules": []},
            },
        )
        response = asyncio.run(patient_report("report_demo"))
        self.assertIn("text/html", response.media_type)
        self.assertIn("Diabetes", response.body.decode("utf-8"))

    def test_patient_report_pdf_endpoint_returns_pdf(self) -> None:
        save_patient_session(
            "report_pdf_demo",
            {
                "language": "en",
                "last_result": {
                    "graph_title": "Burnout",
                    "score_total": 3,
                    "risk_band": {"label": "Moderate burnout risk", "meaning": "Some signs are present."},
                },
                "selected_graph": {"topic": "stress", "report_rules": ["burnout", "summarize exhaustion"]},
            },
        )
        response = asyncio.run(patient_report_pdf("report_pdf_demo"))
        self.assertIn("application/pdf", response.media_type)
        self.assertTrue(response.body.startswith(b"%PDF-1.4"))

    def test_patient_report_pdf_route_is_not_shadowed_by_html_route(self) -> None:
        save_patient_session(
            "report_pdf_route_demo",
            {
                "language": "en",
                "last_result": {
                    "graph_title": "Burnout",
                    "score_total": 3,
                    "risk_band": {"label": "Moderate burnout risk", "meaning": "Some signs are present."},
                },
                "selected_graph": {"topic": "stress", "report_rules": ["burnout", "summarize exhaustion"]},
            },
        )
        client = TestClient(patient_app)
        response = client.get("/report/report_pdf_route_demo.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response.headers.get("content-type", ""))

    def test_show_last_report_includes_report_links(self) -> None:
        result = asyncio.run(
            show_last_report(
                {
                    "language": "ru",
                    "conversation_id": "report_links_demo",
                    "last_result": {
                        "graph_title": "Stress",
                        "score_total": 3,
                        "risk_band": {"label": "moderate burnout risk", "meaning": "Some signs are present."},
                    },
                }
            )
        )
        self.assertIn("/report/report_links_demo", result["assistant_reply"])
        self.assertIn(".pdf", result["assistant_reply"])


if __name__ == "__main__":
    unittest.main()
