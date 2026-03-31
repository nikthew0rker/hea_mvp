import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from shared.config import get_settings
from shared.http_client import post_json
from shared.input_normalizer import detect_language
from shared.prompt_loader import load_json_file
from shared.published_graph_store import publish_graph
from shared.together_client import TogetherAIClient

settings = get_settings()
dp = Dispatcher()

CONTROLLER_POLICY = load_json_file("config/specialist_controller_policy.json")


@dataclass
class SpecialistSession:
    chat_id: int
    conversation_id: str
    language: str = "ru"
    draft: dict[str, Any] = field(default_factory=dict)
    compiled_graph_id: str | None = None
    last_compiled_graph: dict[str, Any] | None = None
    history: list[dict[str, str]] = field(default_factory=list)
    current_focus: str | None = None


SESSIONS: dict[int, SpecialistSession] = {}


def get_or_create_session(chat_id: int) -> SpecialistSession:
    if chat_id not in SESSIONS:
        SESSIONS[chat_id] = SpecialistSession(
            chat_id=chat_id,
            conversation_id=f"specialist_chat_{chat_id}"
        )
    return SESSIONS[chat_id]


def trim_history(history: list[dict[str, str]], max_items: int = 12) -> list[dict[str, str]]:
    return history[-max_items:]


def draft_summary(draft: dict[str, Any]) -> dict[str, Any]:
    understood = draft.get("understood", {}) or {}
    return {
        "topic": understood.get("topic"),
        "target_audience": understood.get("target_audience"),
        "questions_count": len(draft.get("candidate_questions", []) or []),
        "risk_bands_count": len(draft.get("candidate_risk_bands", []) or []),
        "has_scoring": bool((draft.get("candidate_scoring_rules") or {}).get("method")),
        "missing_fields": draft.get("missing_fields", []) or [],
        "has_report_requirements": bool(draft.get("candidate_report_requirements")),
        "has_safety_requirements": bool(draft.get("candidate_safety_requirements"))
    }


async def call_definition_agent(session: SpecialistSession, text: str, operation: str = "update") -> dict[str, Any]:
    return await post_json(
        f"{settings.definition_agent_url}/draft",
        {
            "specialist_text": text,
            "conversation_id": session.conversation_id,
            "current_draft": session.draft,
            "current_language": session.language,
            "conversation_summary": None,
            "operation": operation
        }
    )


async def call_compiler_agent(session: SpecialistSession) -> dict[str, Any]:
    return await post_json(
        f"{settings.compiler_agent_url}/compile",
        {"draft": session.draft}
    )


def view_preview(draft: dict[str, Any]) -> dict[str, Any]:
    understood = draft.get("understood", {}) or {}
    questions = draft.get("candidate_questions", []) or []
    scoring = draft.get("candidate_scoring_rules", {}) or {}
    risk_bands = draft.get("candidate_risk_bands", []) or []
    missing_fields = draft.get("missing_fields", []) or []

    return {
        "topic": understood.get("topic"),
        "target_audience": understood.get("target_audience"),
        "questions_count": len(questions),
        "risk_bands_count": len(risk_bands),
        "scoring": scoring,
        "missing_fields": missing_fields
    }


def view_questions(draft: dict[str, Any]) -> dict[str, Any]:
    return {"questions": draft.get("candidate_questions", []) or []}


def view_scoring(draft: dict[str, Any]) -> dict[str, Any]:
    return {"scoring": draft.get("candidate_scoring_rules", {}) or {}}


def view_risk_bands(draft: dict[str, Any]) -> dict[str, Any]:
    return {"risk_bands": draft.get("candidate_risk_bands", []) or []}


def view_report_rules(draft: dict[str, Any]) -> dict[str, Any]:
    return {"report_rules": draft.get("candidate_report_requirements", []) or []}


def view_safety_rules(draft: dict[str, Any]) -> dict[str, Any]:
    return {"safety_rules": draft.get("candidate_safety_requirements", []) or []}


def fallback_action_from_message(message: str) -> str:
    low = message.lower().strip()

    if "опубли" in low or "publish" in low:
        return "PUBLISH_GRAPH"
    if "скомпил" in low or "compile" in low:
        return "COMPILE_DRAFT"
    if ("покажи" in low and "вопрос" in low) or "show questions" in low:
        return "SHOW_QUESTIONS"
    if ("покажи" in low and "скор" in low) or "show scoring" in low:
        return "SHOW_SCORING"
    if ("покажи" in low and "risk" in low) or ("покажи" in low and "диапаз" in low) or "show risk" in low:
        return "SHOW_RISK_BANDS"
    if "что ты понял" in low or "что получилось" in low or "preview" in low or "what did you understand" in low:
        return "SHOW_PREVIEW"
    if "измени" in low or "поменяй" in low or "change" in low or "edit" in low or "убери" in low or "добавь" in low:
        return "APPLY_EDIT_INSTRUCTION"
    if "что дальше" in low or "what next" in low:
        return "EXPLAIN_NEXT_STEP"
    return "UPDATE_DRAFT_FROM_INPUT"


async def controller_plan(session: SpecialistSession, latest_message: str) -> dict[str, Any]:
    llm = TogetherAIClient(model=settings.specialist_controller_model)

    system_prompt = (
        "You are the specialist-side controller for a Telegram copilot that helps build "
        "health-assessment graphs.\n\n"
        f"Policy:\n{json.dumps(CONTROLLER_POLICY, ensure_ascii=False, indent=2)}\n\n"
        "Return only valid JSON with keys:\n"
        "- action\n"
        "- confidence\n"
        "- reason_short\n"
        "- clarification_target\n\n"
        "Rules:\n"
        "- choose exactly one action from allowed_actions\n"
        "- if the user asks what you understood, choose SHOW_PREVIEW\n"
        "- if the user asks to show questions, choose SHOW_QUESTIONS\n"
        "- if the user asks to show scoring, choose SHOW_SCORING\n"
        "- if the user asks to show risk bands, choose SHOW_RISK_BANDS\n"
        "- if the user pasted new medical content, choose UPDATE_DRAFT_FROM_INPUT\n"
        "- if the user asks to change existing draft content, choose APPLY_EDIT_INSTRUCTION\n"
        "- if the user asks to publish after compilation, choose PUBLISH_GRAPH\n"
        "- if the user intent is unclear, choose ASK_CLARIFICATION\n"
        "- stay inside the graph-building workflow\n"
        "- do not provide diagnosis or treatment\n"
    )

    user_payload = {
        "latest_message": latest_message,
        "language": session.language,
        "current_focus": session.current_focus,
        "compiled_graph_id": session.compiled_graph_id,
        "draft_summary": draft_summary(session.draft),
        "recent_history": trim_history(session.history)
    }

    try:
        result = await llm.complete_json(
            system_prompt=system_prompt,
            user_prompt=json.dumps(user_payload, ensure_ascii=False, indent=2)
        )
    except Exception:
        result = None

    if not isinstance(result, dict):
        return {
            "action": fallback_action_from_message(latest_message),
            "confidence": 0.35,
            "reason_short": "fallback",
            "clarification_target": None
        }

    action = result.get("action")
    if action not in CONTROLLER_POLICY["allowed_actions"]:
        action = "ASK_CLARIFICATION"

    try:
        confidence = float(result.get("confidence", 0.5))
    except Exception:
        confidence = 0.5

    return {
        "action": action,
        "confidence": confidence,
        "reason_short": str(result.get("reason_short", "")),
        "clarification_target": result.get("clarification_target")
    }


def fallback_render_reply(language: str, action: str, tool_result: dict[str, Any]) -> str:
    if language == "ru":
        if action == "PUBLISH_GRAPH":
            if tool_result.get("status") == "ok":
                return (
                    f"Граф опубликован. Активный graph_id: {tool_result.get('published_graph_id')}.\n\n"
                    f"Теперь можно переходить к тесту patient assistant."
                )
            return "Не удалось опубликовать граф. Сначала нужно успешно собрать compiled graph."
        if action == "COMPILE_DRAFT":
            if tool_result.get("status") == "ok" and isinstance(tool_result.get("compile_result"), dict):
                cr = tool_result["compile_result"]
                if cr.get("status") == "compiled":
                    return f"Граф успешно собран. graph_id: {cr.get('graph_version_id')}. Можно публиковать."
            return "Не удалось собрать граф. Проверь draft и попробуй ещё раз."
        if action == "SHOW_PREVIEW":
            return "Вот preview текущего draft."
        if action == "SHOW_QUESTIONS":
            return "Вот вопросы, которые сейчас есть в draft."
        if action == "SHOW_SCORING":
            return "Вот текущий scoring."
        if action == "SHOW_RISK_BANDS":
            return "Вот текущие risk bands."
        if action == "APPLY_EDIT_INSTRUCTION":
            return "Я применил правку к draft. Могу показать результат или продолжить редактирование."
        if action == "UPDATE_DRAFT_FROM_INPUT":
            return "Я обновил draft на основе присланного материала. Могу показать, что получилось."
        if action == "ASK_CLARIFICATION":
            return "Уточни, пожалуйста, что именно ты хочешь сделать с текущим draft."
        return "Ок, продолжаем работу с draft."
    else:
        if action == "PUBLISH_GRAPH":
            if tool_result.get("status") == "ok":
                return (
                    f"The graph is published. Active graph_id: {tool_result.get('published_graph_id')}.\n\n"
                    f"You can now move to patient assistant testing."
                )
            return "I could not publish the graph. The compiled graph must exist first."
        if action == "COMPILE_DRAFT":
            if tool_result.get("status") == "ok" and isinstance(tool_result.get("compile_result"), dict):
                cr = tool_result["compile_result"]
                if cr.get("status") == "compiled":
                    return f"The graph was compiled successfully. graph_id: {cr.get('graph_version_id')}. You can publish it now."
            return "I could not compile the graph. Please check the draft and try again."
        if action == "SHOW_PREVIEW":
            return "Here is the current draft preview."
        if action == "SHOW_QUESTIONS":
            return "Here are the questions currently in the draft."
        if action == "SHOW_SCORING":
            return "Here is the current scoring."
        if action == "SHOW_RISK_BANDS":
            return "Here are the current risk bands."
        if action == "APPLY_EDIT_INSTRUCTION":
            return "I applied the edit to the draft. I can show the result or continue editing."
        if action == "UPDATE_DRAFT_FROM_INPUT":
            return "I updated the draft from the material you sent. I can show what I understood."
        if action == "ASK_CLARIFICATION":
            return "Please clarify what exactly you want to do with the current draft."
        return "Okay, let's continue working with the draft."


async def render_final_reply(session: SpecialistSession, latest_message: str, action: str, tool_result: dict[str, Any]) -> str:
    llm = TogetherAIClient(model=settings.specialist_controller_model)

    system_prompt = (
        "You are a specialist-facing Telegram copilot for building health-assessment graphs.\n"
        "Write one natural assistant reply in the user's current language.\n\n"
        "Rules:\n"
        "- do not output raw JSON\n"
        "- do not sound like an API or state machine\n"
        "- be helpful and concise\n"
        "- explain what was understood or changed\n"
        "- suggest the most useful next step\n"
        "- stay inside the graph-building workflow\n"
        "- do not provide diagnosis, treatment plans, or medication advice\n"
    )

    user_payload = {
        "language": session.language,
        "latest_message": latest_message,
        "action": action,
        "draft_summary": draft_summary(session.draft),
        "tool_result": tool_result,
        "current_focus": session.current_focus
    }

    try:
        reply = await llm.complete_text(
            system_prompt=system_prompt,
            user_prompt=json.dumps(user_payload, ensure_ascii=False, indent=2)
        )
        if isinstance(reply, str) and reply.strip():
            return reply.strip()
    except Exception:
        pass

    return fallback_render_reply(session.language, action, tool_result)


async def execute_action(session: SpecialistSession, action: str, latest_message: str) -> dict[str, Any]:
    if action == "RESTART_WORKFLOW":
        session.draft = {}
        session.compiled_graph_id = None
        session.last_compiled_graph = None
        session.current_focus = None
        return {"status": "reset"}

    if action == "SHOW_PREVIEW":
        session.current_focus = "preview"
        return {"status": "ok", "preview": view_preview(session.draft)}

    if action == "SHOW_QUESTIONS":
        session.current_focus = "questions"
        return {"status": "ok", "questions": view_questions(session.draft)}

    if action == "SHOW_SCORING":
        session.current_focus = "scoring"
        return {"status": "ok", "scoring": view_scoring(session.draft)}

    if action == "SHOW_RISK_BANDS":
        session.current_focus = "risk_bands"
        return {"status": "ok", "risk_bands": view_risk_bands(session.draft)}

    if action == "SHOW_REPORT_RULES":
        session.current_focus = "report_rules"
        return {"status": "ok", "report_rules": view_report_rules(session.draft)}

    if action == "SHOW_SAFETY_RULES":
        session.current_focus = "safety_rules"
        return {"status": "ok", "safety_rules": view_safety_rules(session.draft)}

    if action == "UPDATE_DRAFT_FROM_INPUT":
        session.current_focus = "draft_update"
        result = await call_definition_agent(session, latest_message, operation="update")
        session.draft = result.get("draft", {}) or session.draft
        session.compiled_graph_id = None
        session.last_compiled_graph = None
        return {"status": "ok", "draft_update": result}

    if action == "APPLY_EDIT_INSTRUCTION":
        session.current_focus = "draft_edit"
        result = await call_definition_agent(session, latest_message, operation="edit")
        session.draft = result.get("draft", {}) or session.draft
        session.compiled_graph_id = None
        session.last_compiled_graph = None
        return {"status": "ok", "draft_edit": result}

    if action == "COMPILE_DRAFT":
        session.current_focus = "compile"
        if not session.draft:
            return {"status": "error", "message": "No draft available"}

        result = await call_compiler_agent(session)
        if result.get("status") == "compiled":
            session.compiled_graph_id = result.get("graph_version_id")
            compiled_graph = result.get("graph")
            if isinstance(compiled_graph, dict):
                session.last_compiled_graph = compiled_graph
            else:
                session.last_compiled_graph = {
                    "graph_version_id": session.compiled_graph_id,
                    "source_draft": session.draft,
                }
        return {"status": "ok", "compile_result": result}

    if action == "PUBLISH_GRAPH":
        session.current_focus = "publish"
        if not session.compiled_graph_id:
            return {"status": "error", "message": "Graph is not compiled yet"}

        graph_payload = session.last_compiled_graph or {
            "graph_version_id": session.compiled_graph_id,
            "source_draft": session.draft,
        }

        published = publish_graph(
            graph_id=session.compiled_graph_id,
            graph_payload=graph_payload,
            metadata={
                "draft_summary": draft_summary(session.draft),
                "conversation_id": session.conversation_id,
            },
        )

        return {
            "status": "ok",
            "published_graph_id": session.compiled_graph_id,
            "publish_result": published,
        }

    if action == "EXPLAIN_NEXT_STEP":
        session.current_focus = "next_step"
        return {
            "status": "ok",
            "next_step_hint": {
                "draft_summary": draft_summary(session.draft),
                "compiled_graph_id": session.compiled_graph_id
            }
        }

    if action == "ASK_CLARIFICATION":
        session.current_focus = "clarification"
        return {"status": "ok", "clarification_needed": True}

    return {"status": "ok", "direct_reply": True}


async def handle_specialist_text(session: SpecialistSession, latest_message: str) -> str:
    session.language = detect_language(latest_message)

    low = latest_message.lower().strip()
    if low == "/start":
        return (
            "Привет. Я помогу тебе собрать health-assessment graph для Hea."
            if session.language == "ru"
            else
            "Hi. I will help you build a health-assessment graph for Hea."
        )
    if low == "/help":
        return (
            "Я могу принимать новый медицинский контент, показывать текущий draft, отдельно показывать вопросы / scoring / risk bands, вносить правки, компилировать и публиковать граф."
            if session.language == "ru"
            else
            "I can accept new medical content, show the current draft, show questions / scoring / risk bands separately, apply edits, compile, and publish the graph."
        )

    plan = await controller_plan(session, latest_message)
    action = plan["action"]
    tool_result = await execute_action(session, action, latest_message)
    reply = await render_final_reply(session, latest_message, action, tool_result)

    session.history.append({"role": "user", "content": latest_message})
    session.history.append({"role": "assistant", "content": reply})
    session.history = trim_history(session.history, max_items=16)

    return reply


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    session = get_or_create_session(message.chat.id)
    session.language = "ru"
    await message.answer(
        "Привет. Я помогу тебе собрать assessment graph для Hea. "
        "Можешь прислать идею, шкалу, guideline, noisy текст, а я буду вести сессию как рабочий draft."
    )


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    session = get_or_create_session(message.chat.id)
    await message.answer(
        "Я умею: принимать новый медицинский контент, показывать текущий draft, отдельно показывать вопросы / scoring / risk bands, вносить правки, компилировать и публиковать граф."
        if session.language == "ru"
        else
        "I can accept new medical content, show the current draft, show questions / scoring / risk bands separately, apply edits, compile, and publish the graph."
    )


@dp.message(F.text)
async def specialist_message_handler(message: Message) -> None:
    session = get_or_create_session(message.chat.id)
    reply = await handle_specialist_text(session, message.text)
    await message.answer(reply)


async def main() -> None:
    bot = Bot(token=settings.specialist_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
