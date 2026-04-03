from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from hea.shared.authoring_models import CriticReview, EditOperation
from hea.shared.config import get_settings
from hea.shared.noisy_text import extract_candidate_update, infer_artifact_type, infer_topic
from hea.shared.patient_models import PatientIntentDecision
from hea.shared.scaffold_registry import get_scaffold, infer_scaffold_framework, infer_scaffold_topic


class TogetherAIClient:
    JSON_UNSAFE_MODELS = {
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    }

    def __init__(self, model: str | None = None):
        settings = get_settings()
        self.api_key = settings.together_api_key
        self.model = model or settings.together_model
        self.provider_timeout_seconds = settings.provider_timeout_seconds

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            return self._heuristic_json(user_prompt)

        model = self._json_safe_model()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None
        delays = [0.6, 1.2, 2.0]

        for attempt, delay in enumerate(delays, start=1):
            try:
                async with httpx.AsyncClient(timeout=self.provider_timeout_seconds) as client:
                    response = await client.post(
                        "https://api.together.xyz/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = self._extract_json(content)
                    if parsed:
                        return parsed
                    # Empty/invalid JSON from provider should still degrade gracefully.
                    return self._heuristic_json(user_prompt)

            except (httpx.HTTPStatusError, httpx.RequestError, KeyError, IndexError, ValueError) as exc:
                last_error = exc
                if not self._is_retryable(exc) or attempt == len(delays):
                    break
                await asyncio.sleep(delay)

        # Never propagate transient provider failures into controller 500s.
        return self._heuristic_json(user_prompt)

    def _json_safe_model(self) -> str:
        if self.model not in self.JSON_UNSAFE_MODELS:
            return self.model
        settings = get_settings()
        fallback_chain = [
            settings.controller_model,
            settings.specialist_critic_model,
            settings.specialist_compiler_model,
            "MiniMaxAI/MiniMax-M2.5",
        ]
        for candidate in fallback_chain:
            if candidate and candidate not in self.JSON_UNSAFE_MODELS:
                return candidate
        return self.model

    def _is_retryable(self, exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            return code in {408, 409, 425, 429, 500, 502, 503, 504}
        if isinstance(exc, httpx.RequestError):
            return True
        return False

    def _extract_json(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            parts = text.split("\n", 1)
            text = parts[1] if len(parts) > 1 else text
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _heuristic_json(self, user_prompt: str) -> dict[str, Any]:
        prompt = user_prompt.lower()

        if "analysis_mode" in prompt:
            try:
                payload = json.loads(user_prompt)
            except Exception:
                payload = {}

            if payload.get("analysis_mode") == "specialist_turn":
                message = str(payload.get("specialist_message", ""))
                low = " ".join(message.lower().strip().split())
                pending_exists = bool(payload.get("pending_proposal_exists"))
                draft = payload.get("current_draft") or {}
                topic = ((draft.get("understood") or {}).get("topic")) or infer_topic(message)

                decision = {
                    "next_action": "DISCUSS",
                    "should_prepare_proposal": False,
                    "should_apply_pending": False,
                    "follow_up_question": "",
                    "action_rationale": "default discussion fallback",
                    "confidence": 0.55,
                    "recognized_topic": topic,
                }

                if any(token in low for token in ["show detailed draft", "драфт подробно", "подробный драфт"]):
                    decision.update({"next_action": "SHOW_DETAILED_DRAFT", "action_rationale": "detailed draft requested", "confidence": 0.95})
                    return decision
                if any(token in low for token in ["откуда ты взял вопросы", "откуда вопросы", "where did the questions come from"]):
                    decision.update({"next_action": "EXPLAIN_QUESTION_SOURCE", "action_rationale": "question source requested", "confidence": 0.95})
                    return decision
                if any(token in low for token in ["show draft", "show preview", "покажи драфт", "что ты понял"]):
                    decision.update({"next_action": "SHOW_PREVIEW", "action_rationale": "draft preview requested", "confidence": 0.95})
                    return decision
                if any(token in low for token in ["show diff", "покажи diff", "покажи изменения", "show changes"]):
                    decision.update({"next_action": "SHOW_DIFF", "action_rationale": "diff requested", "confidence": 0.97})
                    return decision
                if any(token in low for token in ["show versions", "покажи версии", "версии"]):
                    decision.update({"next_action": "SHOW_VERSIONS", "action_rationale": "version history requested", "confidence": 0.97})
                    return decision
                if re.search(r"(?:rollback|откати(?:\s+на)?|верни\s+на)\s*v?\d+", low):
                    decision.update({"next_action": "ROLLBACK_DRAFT", "action_rationale": "rollback requested", "confidence": 0.97})
                    return decision
                if any(token in low for token in ["show questions", "покажи вопросы"]):
                    decision.update({"next_action": "SHOW_QUESTIONS", "action_rationale": "questions requested", "confidence": 0.95})
                    return decision
                if any(token in low for token in ["show scoring", "покажи скоринг", "покажи scoring"]):
                    decision.update({"next_action": "SHOW_SCORING", "action_rationale": "scoring requested", "confidence": 0.95})
                    return decision
                if any(token in low for token in ["show risks", "покажи риски", "покажи risks"]):
                    decision.update({"next_action": "SHOW_RISKS", "action_rationale": "risk bands requested", "confidence": 0.95})
                    return decision
                if any(token in low for token in ["compile", "скомпил"]):
                    decision.update({"next_action": "COMPILE", "action_rationale": "compile requested", "confidence": 0.98})
                    return decision
                if any(token in low for token in ["publish", "опубли"]):
                    decision.update({"next_action": "PUBLISH", "action_rationale": "publish requested", "confidence": 0.98})
                    return decision
                if any(token in low for token in ["help", "помощь", "что умеешь"]):
                    decision.update({"next_action": "SHOW_HELP", "action_rationale": "help requested", "confidence": 0.95})
                    return decision
                if pending_exists and low in {"да", "ок", "окей", "давай", "примени", "применяй", "yes", "ok", "apply"}:
                    decision.update(
                        {
                            "next_action": "APPLY_PENDING_PROPOSAL",
                            "should_apply_pending": True,
                            "action_rationale": "pending proposal confirmation detected",
                            "confidence": 0.98,
                        }
                    )
                    return decision
                if pending_exists and any(token in low for token in ["примени только вопросы", "apply questions only"]):
                    decision.update({"next_action": "APPLY_PENDING_PROPOSAL", "should_apply_pending": True, "action_rationale": "apply questions only requested", "confidence": 0.98})
                    return decision
                if pending_exists and any(token in low for token in ["примени только риски", "apply risks only"]):
                    decision.update({"next_action": "APPLY_PENDING_PROPOSAL", "should_apply_pending": True, "action_rationale": "apply risks only requested", "confidence": 0.98})
                    return decision

                build_tokens = ["создай ", "собери ", "сгенерируй ", "добавь ", "обнови ", "внеси ", "примени ", "generate ", "create ", "apply ", "update "]
                looks_like_build = any(low.startswith(token) for token in build_tokens) or "в драфт" in low or "черновик" in low
                has_structure = (
                    ("\n" in message and any(line.strip().startswith(("-", "*")) for line in message.splitlines()))
                    or bool(re.search(r"(?m)^\s*\d+[\.)]\s+", message))
                    or len(message.strip()) >= 180
                    or any(token in low for token in ["guideline", "score", "scoring", "risk band", "вопрос", "шкала", "скоринг", "риски", "анамнез", "сценарий", "question"])
                )
                looks_like_goal = any(
                    token in low
                    for token in ["я хочу собрать", "хочу собрать", "хочу сделать", "мы собираем", "нужен сценарий", "тема:", "topic:", "findrisk", "диабет", "sleep", "stress", "assessment"]
                )

                if looks_like_build:
                    decision.update(
                        {
                            "next_action": "UPDATE_DRAFT",
                            "should_prepare_proposal": False,
                            "action_rationale": "explicit build/update request detected",
                            "confidence": 0.86,
                            "recognized_topic": topic,
                        }
                    )
                    return decision

                if looks_like_goal or has_structure:
                    decision.update(
                        {
                            "next_action": "DISCUSS",
                            "should_prepare_proposal": True,
                            "action_rationale": "goal or structured material detected; prepare proposal first",
                            "confidence": 0.82,
                            "recognized_topic": topic,
                            "follow_up_question": (
                                "Хотите, чтобы я сначала предложил draft scaffold, или будете сами задавать вопросы и скоринг?"
                                if re.search(r"[а-яА-ЯёЁ]", message)
                                else "Do you want me to propose a draft scaffold first, or will you specify the questions and scoring yourself?"
                            ),
                        }
                    )
                    return decision

                return decision

            if payload.get("analysis_mode") == "patient_turn":
                message = str(payload.get("patient_message", ""))
                low = " ".join(message.lower().strip().split())
                mode = str(payload.get("current_mode") or "free_conversation")
                candidate_count = int(payload.get("candidate_count") or 0)
                red_flag_level = "none"
                if any(token in low for token in ["боль в груди", "не могу дышать", "chest pain", "shortness of breath"]):
                    red_flag_level = "emergency"
                elif any(token in low for token in ["сильная боль", "кровь", "bleeding", "high fever"]):
                    red_flag_level = "urgent"

                if low in {"/start", "привет", "hello", "hi"}:
                    return PatientIntentDecision(next_action="RESET_AND_GREET", confidence=0.98, rationale="greeting", red_flag_level="none", symptom_summary=None).model_dump(mode="json")
                if any(token in low for token in ["что умеешь", "what can you do", "capabilities"]):
                    return PatientIntentDecision(next_action="SHOW_CAPABILITIES", confidence=0.95, rationale="capabilities", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                if red_flag_level in {"urgent", "emergency"} and mode == "free_conversation":
                    return PatientIntentDecision(next_action="RED_FLAG_GUIDANCE", confidence=0.94, rationale="red flag detected", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                if mode == "awaiting_selection" and low.isdigit() and candidate_count > 0:
                    return PatientIntentDecision(next_action="SELECT_CANDIDATE", confidence=0.95, rationale="candidate selection", red_flag_level=red_flag_level, selected_candidate_index=int(low), symptom_summary=message[:160]).model_dump(mode="json")
                if mode == "awaiting_consent":
                    if low in {"да", "yes", "ok", "start", "давай"}:
                        return PatientIntentDecision(next_action="START_ASSESSMENT", confidence=0.95, rationale="start assessment", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    if low in {"нет", "no", "later", "not now"}:
                        return PatientIntentDecision(next_action="DECLINE", confidence=0.95, rationale="decline assessment", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    return PatientIntentDecision(next_action="RESTATE_CONSENT", confidence=0.72, rationale="ambiguous consent reply", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                if mode == "assessment_in_progress":
                    if low in {"пауза", "pause"}:
                        return PatientIntentDecision(next_action="PAUSE", confidence=0.95, rationale="pause", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    if any(token in low for token in ["результат", "итог", "result", "summary"]):
                        return PatientIntentDecision(next_action="SHOW_CURRENT_RESULT", confidence=0.9, rationale="result request", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    if any(token in low for token in ["отчет", "отчёт", "report"]):
                        return PatientIntentDecision(next_action="SHOW_CURRENT_REPORT", confidence=0.9, rationale="report request", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    if any(token in low for token in ["объясни", "explain"]):
                        return PatientIntentDecision(next_action="EXPLAIN_CURRENT_RESULT", confidence=0.9, rationale="explain result", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    return PatientIntentDecision(next_action="RUN_RUNTIME_SUBGRAPH", confidence=0.85, rationale="assessment answer", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                if mode == "paused_assessment":
                    if low in {"продолжить", "resume", "continue", "дальше", "да"}:
                        return PatientIntentDecision(next_action="RESUME", confidence=0.95, rationale="resume paused assessment", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    return PatientIntentDecision(next_action="SHOW_PAUSED", confidence=0.8, rationale="paused state", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                if mode == "post_assessment":
                    if any(token in low for token in ["результат", "итог", "result", "summary"]):
                        return PatientIntentDecision(next_action="SHOW_LAST_RESULT", confidence=0.9, rationale="last result", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    if any(token in low for token in ["отчет", "отчёт", "report"]):
                        return PatientIntentDecision(next_action="SHOW_LAST_REPORT", confidence=0.9, rationale="last report", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    if any(token in low for token in ["объясни", "explain"]):
                        return PatientIntentDecision(next_action="EXPLAIN_LAST_RESULT", confidence=0.9, rationale="last explain", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                    return PatientIntentDecision(next_action="SHOW_POST_OPTIONS", confidence=0.72, rationale="ambiguous post-assessment turn", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")
                return PatientIntentDecision(next_action="SEARCH", confidence=0.7, rationale="default search", red_flag_level=red_flag_level, symptom_summary=message[:160]).model_dump(mode="json")

            if payload.get("analysis_mode") == "specialist_edit_operation":
                message = str(payload.get("specialist_message", ""))
                low = " ".join(message.lower().strip().split())
                if any(token in low for token in ["show detailed draft", "драфт подробно", "подробный драфт"]):
                    return EditOperation(intent_type="show_detailed_draft", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["откуда ты взял вопросы", "откуда вопросы", "where did the questions come from"]):
                    return EditOperation(intent_type="explain_question_source", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["show draft", "show preview", "покажи драфт", "что ты понял"]):
                    return EditOperation(intent_type="show_preview", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["show diff", "покажи diff", "покажи изменения", "show changes"]):
                    return EditOperation(intent_type="show_diff", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["show versions", "покажи версии", "версии"]):
                    return EditOperation(intent_type="show_versions", requires_confirmation=False).model_dump(mode="json")
                rollback_match = re.search(r"(?:rollback|откати(?:\s+на)?|верни\s+на)\s*v?(\d+)", low)
                if rollback_match:
                    return EditOperation(intent_type="rollback_draft", requires_confirmation=False, rollback_version_id=int(rollback_match.group(1))).model_dump(mode="json")
                if any(token in low for token in ["show questions", "покажи вопросы"]):
                    return EditOperation(intent_type="show_questions", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["show scoring", "покажи скоринг", "покажи scoring"]):
                    return EditOperation(intent_type="show_scoring", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["show risks", "покажи риски", "покажи risks"]):
                    return EditOperation(intent_type="show_risks", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["compile", "скомпил"]):
                    return EditOperation(intent_type="compile", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["publish", "опубли"]):
                    return EditOperation(intent_type="publish", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["примени предложение", "примени", "apply proposal", "apply"]) and bool(payload.get("pending_proposal_exists")):
                    return EditOperation(intent_type="apply_pending_proposal", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["примени только вопросы", "apply questions only"]) and bool(payload.get("pending_proposal_exists")):
                    return EditOperation(intent_type="apply_questions_only", target_section="questions", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["примени только риски", "apply risks only"]) and bool(payload.get("pending_proposal_exists")):
                    return EditOperation(intent_type="apply_risks_only", target_section="risk_bands", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["примени только секции", "apply sections only"]) and bool(payload.get("pending_proposal_exists")):
                    return EditOperation(intent_type="apply_sections_only", target_section="anamnesis_sections", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["примени только правила", "apply rules only"]) and bool(payload.get("pending_proposal_exists")):
                    return EditOperation(intent_type="apply_rules_only", target_section="rule_nodes", requires_confirmation=False).model_dump(mode="json")
                if any(token in low for token in ["интерпретация суммы баллов", "оценка рисков", "risk bands", "risk band", "интерпретация риска", "диапазон риска"]):
                    return EditOperation(intent_type="replace_risk_bands", target_section="risk_bands", requires_compilation=True).model_dump(mode="json")
                if any(token in low for token in ["анамнез", "anamnesis"]) and any(low.startswith(token) for token in ["добавь ", "add ", "append ", "создай ", "собери "]):
                    return EditOperation(intent_type="add_anamnesis_section", target_section="anamnesis_sections", requires_compilation=True).model_dump(mode="json")
                if any(token in low for token in ["клиническое правило", "clinical rule", "rule node", "диагностическ"]) and any(low.startswith(token) for token in ["добавь ", "add ", "replace ", "update ", "обнови ", "внеси "]):
                    return EditOperation(intent_type="replace_rule_nodes", target_section="rule_nodes", requires_compilation=True).model_dump(mode="json")
                if any(low.startswith(token) for token in ["добавь ", "обнови ", "внеси ", "replace ", "append ", "update ", "создай ", "собери "]):
                    return EditOperation(intent_type="replace_questions_from_text", target_section="questions", requires_compilation=True).model_dump(mode="json")
                if any(token in low for token in ["дескипшен удали", "описание удали", "regenerate description", "сгенерируй описание"]):
                    return EditOperation(intent_type="regenerate_description", target_section="description", requires_compilation=False).model_dump(mode="json")
                if "findrisk" in low:
                    return EditOperation(intent_type="set_framework", target_section="framework", framework="findrisk", requires_compilation=True).model_dump(mode="json")
                return EditOperation(intent_type="discuss", requires_confirmation=True).model_dump(mode="json")

        if "questionnaire_spec" in prompt and "should_block_apply" in prompt:
            try:
                payload = json.loads(user_prompt)
                spec = payload.get("questionnaire_spec") or {}
            except Exception:
                spec = {}
            questions = spec.get("questions") or []
            artifact_type = str(spec.get("artifact_type") or "questionnaire")
            findings = []
            should_block = False
            if any(len(question.get("options") or []) == 2 for question in questions) and str(spec.get("framework") or "").lower() == "findrisk":
                findings.append({"severity": "error", "message": "FINDRISC-like questions appear underspecified.", "field_path": "questions"})
                should_block = True
            if artifact_type == "anamnesis_flow" and not (spec.get("anamnesis_sections") or []):
                findings.append({"severity": "error", "message": "Anamnesis flow has no sections.", "field_path": "anamnesis_sections"})
                should_block = True
            if artifact_type == "clinical_rule_graph" and not (spec.get("rule_nodes") or []):
                findings.append({"severity": "error", "message": "Clinical rule graph has no rule nodes.", "field_path": "rule_nodes"})
                should_block = True
            return CriticReview(
                is_valid=not should_block,
                severity="error" if should_block else "info",
                findings=findings,
                missing_information=[],
                proposed_repairs=[],
                should_block_apply=should_block,
            ).model_dump(mode="json")

        if "specialist_message" in prompt:
            try:
                payload = json.loads(user_prompt)
                message = str(payload.get("specialist_message", ""))
                current_draft = payload.get("current_draft") or {}
            except Exception:
                message = user_prompt
                current_draft = {}

            extracted = extract_candidate_update(message, current_draft)
            artifact_type = extracted.get("understood", {}).get("artifact_type") or infer_artifact_type(message)
            topic = extracted.get("understood", {}).get("topic") or infer_scaffold_topic(message) or infer_topic(message) or "assessment"
            framework = infer_scaffold_framework(message) or (current_draft.get("understood") or {}).get("framework")

            starter_scaffold = get_scaffold(topic, framework)
            if starter_scaffold and not extracted.get("candidate_questions"):
                extracted["candidate_questions"] = starter_scaffold.get("candidate_questions", [])
            if starter_scaffold and not extracted.get("candidate_risk_bands"):
                extracted["candidate_risk_bands"] = starter_scaffold.get("candidate_risk_bands", [])
            if starter_scaffold and not extracted.get("candidate_scoring_rules"):
                extracted["candidate_scoring_rules"] = starter_scaffold.get("candidate_scoring_rules", {})

            understood = dict(extracted.get("understood") or {})
            understood.setdefault("topic", topic)
            understood.setdefault("description", message[:300])
            understood.setdefault("artifact_type", artifact_type)
            if framework:
                understood.setdefault("framework", framework)
            understood.setdefault("tags", starter_scaffold.get("understood", {}).get("tags", [topic]) if starter_scaffold else [topic])
            understood.setdefault("entry_signals", starter_scaffold.get("understood", {}).get("entry_signals", [topic]) if starter_scaffold else [topic])
            if starter_scaffold:
                understood.setdefault("source_summary", starter_scaffold.get("understood", {}).get("source_summary"))

            extracted["understood"] = understood
            extracted.setdefault("candidate_scoring_rules", {"method": "sum_of_option_scores"})
            extracted.setdefault("candidate_risk_bands", [])
            extracted.setdefault("candidate_anamnesis_sections", [])
            extracted.setdefault("candidate_red_flags", [])
            extracted.setdefault("candidate_assessment_output", None)
            extracted.setdefault("candidate_diagnostic_inputs", [])
            extracted.setdefault("candidate_rule_nodes", [])
            extracted.setdefault("candidate_conclusion_template", None)
            extracted.setdefault("candidate_report_requirements", [])
            extracted.setdefault("candidate_safety_requirements", [])
            extracted.setdefault("missing_fields", [])
            return extracted

        return {"status": "no_match"}
