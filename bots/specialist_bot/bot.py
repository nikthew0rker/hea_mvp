import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from shared.config import get_settings
from shared.http_client import post_json
from shared.input_normalizer import detect_language
from shared.prompt_loader import load_json_file

settings = get_settings()
dp = Dispatcher()

BASE_DIR = Path(__file__).resolve().parents[2]
BOT_POLICY_PATH = BASE_DIR / "config" / "specialist_bot_policy.json"


class SpecialistState(str, Enum):
    IDLE = "idle"
    COLLECTING_DEFINITION = "collecting_definition"
    CLARIFYING_DEFINITION = "clarifying_definition"
    READY_TO_COMPILE = "ready_to_compile"
    COMPILE_IN_PROGRESS = "compile_in_progress"
    COMPILED = "compiled"


class SpecialistIntent(str, Enum):
    GREETING = "greeting"
    LANGUAGE_SWITCH = "language_switch"
    HELP = "help"
    START_OR_CONTINUE_DEFINITION = "start_or_continue_definition"
    ASK_SUMMARY = "ask_summary"
    ASK_WHAT_NEXT = "ask_what_next"
    COMPILE_REQUEST = "compile_request"
    PUBLISH_REQUEST = "publish_request"
    RESTART_REQUEST = "restart_request"


@dataclass
class SpecialistSession:
    chat_id: int
    conversation_id: str
    state: SpecialistState = SpecialistState.IDLE
    language: str = "ru"
    draft: dict[str, Any] = field(default_factory=dict)
    last_structured_result: dict[str, Any] | None = None
    compiled_graph_id: str | None = None


SESSIONS: dict[int, SpecialistSession] = {}


def get_or_create_session(chat_id: int) -> SpecialistSession:
    if chat_id not in SESSIONS:
        SESSIONS[chat_id] = SpecialistSession(
            chat_id=chat_id,
            conversation_id=f"specialist_chat_{chat_id}",
        )
    return SESSIONS[chat_id]


def detect_rule_based_intent(text: str) -> SpecialistIntent | None:
    t = text.lower().strip()
    if any(x in t for x in ["привет", "здравствуй", "здравствуйте", "hello", "hi", "hey"]):
        return SpecialistIntent.GREETING
    if any(x in t for x in ["помощь", "help", "что ты умеешь", "как работать"]):
        return SpecialistIntent.HELP
    if any(x in t for x in ["русский", "по-русски", "english", "speak english", "speak russian"]):
        return SpecialistIntent.LANGUAGE_SWITCH
    if any(x in t for x in ["summary", "черновик", "сводка", "что уже собрано"]):
        return SpecialistIntent.ASK_SUMMARY
    if any(x in t for x in ["что дальше", "what next", "next step"]):
        return SpecialistIntent.ASK_WHAT_NEXT
    if any(x in t for x in ["скомпилируй", "compile", "собери граф"]):
        return SpecialistIntent.COMPILE_REQUEST
    if any(x in t for x in ["publish", "опубликуй", "публикуй"]):
        return SpecialistIntent.PUBLISH_REQUEST
    if any(x in t for x in ["начать заново", "сначала", "restart", "reset"]):
        return SpecialistIntent.RESTART_REQUEST
    return None


def render_greeting(language: str) -> str:
    if language == "ru":
        return (
            "Привет. Я могу общаться по-русски и помочь собрать health-assessment для Hea.\n\n"
            "Ты можешь описать идею в свободной форме: тему, аудиторию, вопросы, шкалу, guideline, "
            "таблицу, кусок статьи или даже сырой noisy текст — я попробую извлечь структуру "
            "и подскажу, чего не хватает."
        )
    return (
        "Hi. I can help you build a health assessment for Hea.\n\n"
        "You can describe the idea in free form: topic, audience, questions, scale, guideline, "
        "table, article fragment, or even a noisy pasted document — I will try to extract structure "
        "and tell you what is still missing."
    )


def render_help(language: str) -> str:
    if language == "ru":
        return (
            "Лучше всего просто прислать материал в свободной форме.\n\n"
            "Я умею работать с:\n"
            "- обычным текстовым описанием\n"
            "- списком вопросов\n"
            "- шкалой с баллами\n"
            "- таблицей порогов риска\n"
            "- кусками guideline\n"
            "- noisy вставками с сайта\n\n"
            "После этого я постараюсь:\n"
            "1. выделить тему\n"
            "2. вытащить вопросы\n"
            "3. распознать scoring\n"
            "4. распознать risk bands\n"
            "5. задать только следующий полезный вопрос"
        )
    return (
        "The best way is to send the material in free form.\n\n"
        "I can work with:\n"
        "- plain text description\n"
        "- question list\n"
        "- scored scale\n"
        "- risk threshold table\n"
        "- guideline fragments\n"
        "- noisy webpage dumps\n\n"
        "Then I will try to:\n"
        "1. identify the topic\n"
        "2. extract questions\n"
        "3. extract scoring\n"
        "4. extract risk bands\n"
        "5. ask only the most useful next question"
    )


def render_what_next(language: str, state: SpecialistState) -> str:
    if language == "ru":
        mapping = {
            SpecialistState.IDLE: "Опиши идею ассессмента или вставь шкалу / guideline — я начну собирать definition.",
            SpecialistState.COLLECTING_DEFINITION: "Я собираю структуру definition. Можно прислать ещё вопросы, таблицу скоринга или пороги риска.",
            SpecialistState.CLARIFYING_DEFINITION: "Сейчас лучше ответить на мой уточняющий вопрос, чтобы закрыть недостающие поля.",
            SpecialistState.READY_TO_COMPILE: "Черновик уже выглядит достаточно полным. Если хочешь, я попробую компиляцию.",
            SpecialistState.COMPILE_IN_PROGRESS: "Сейчас идёт компиляция graph.",
            SpecialistState.COMPILED: "Graph уже собран. Следующий шаг — summary, review или publish.",
        }
        return mapping[state]
    mapping = {
        SpecialistState.IDLE: "Describe the assessment idea or paste a scale / guideline — I will start building the definition.",
        SpecialistState.COLLECTING_DEFINITION: "I am collecting the definition structure. You can send more questions, scoring tables, or risk thresholds.",
        SpecialistState.CLARIFYING_DEFINITION: "The best next step is to answer my clarification question so I can close the missing fields.",
        SpecialistState.READY_TO_COMPILE: "The draft already looks complete enough. If you want, I can try compilation.",
        SpecialistState.COMPILE_IN_PROGRESS: "Graph compilation is currently in progress.",
        SpecialistState.COMPILED: "The graph is already compiled. Next step: summary, review, or publish.",
    }
    return mapping[state]


def render_structured_reply(language: str, result: dict[str, Any]) -> str:
    understood = result.get("understood", {}) or {}
    missing_fields = result.get("missing_fields", []) or []
    status = result.get("status")
    next_question = result.get("suggested_next_question")
    questions = result.get("candidate_questions", []) or []
    risk_bands = result.get("candidate_risk_bands", []) or []

    if language == "ru":
        parts = []
        topic = understood.get("topic")
        audience = understood.get("target_audience")
        questions_count = understood.get("questions_count") or len(questions)

        if topic or audience or questions_count:
            parts.append("Я уже понял следующее:")
            if topic:
                parts.append(f"- тема: {topic}")
            if audience:
                parts.append(f"- аудитория: {audience}")
            if questions_count:
                parts.append(f"- вопросов распознано: {questions_count}")
            if risk_bands:
                parts.append(f"- диапазонов риска распознано: {len(risk_bands)}")
            parts.append("")
        else:
            parts.append("Я частично разобрал материал, но пока структура ещё не полная.")
            parts.append("")

        if status == "ready_to_compile":
            parts.append("Похоже, черновик уже достаточно полный для следующего шага.")
            parts.append("Могу попробовать собрать compiled graph. Напиши: `скомпилируй`.")
            return "\n".join(parts)

        if missing_fields:
            parts.append("Пока ещё не хватает:")
            for item in missing_fields:
                parts.append(f"- {item}")
            parts.append("")

        if next_question:
            parts.append(next_question)
        else:
            parts.append("Можешь прислать следующий кусок материала, и я продолжу собирать definition.")
        return "\n".join(parts)

    parts = []
    topic = understood.get("topic")
    audience = understood.get("target_audience")
    questions_count = understood.get("questions_count") or len(questions)

    if topic or audience or questions_count:
        parts.append("Here is what I already understand:")
        if topic:
            parts.append(f"- topic: {topic}")
        if audience:
            parts.append(f"- target audience: {audience}")
        if questions_count:
            parts.append(f"- extracted questions: {questions_count}")
        if risk_bands:
            parts.append(f"- extracted risk bands: {len(risk_bands)}")
        parts.append("")
    else:
        parts.append("I partially parsed the material, but the structure is not complete yet.")
        parts.append("")

    if status == "ready_to_compile":
        parts.append("The draft looks complete enough for the next step.")
        parts.append("I can try to build the compiled graph now. Type: `compile`.")
        return "\n".join(parts)

    if missing_fields:
        parts.append("I am still missing:")
        for item in missing_fields:
            parts.append(f"- {item}")
        parts.append("")

    if next_question:
        parts.append(next_question)
    else:
        parts.append("You can send the next piece of material and I will continue building the definition.")
    return "\n".join(parts)


async def call_definition_agent(session: SpecialistSession, text: str) -> dict[str, Any]:
    return await post_json(
        f"{settings.definition_agent_url}/draft",
        {
            "specialist_text": text,
            "conversation_id": session.conversation_id,
            "current_draft": session.draft,
            "current_language": session.language,
            "conversation_summary": None,
        },
    )


async def call_compiler_agent(session: SpecialistSession) -> dict[str, Any]:
    return await post_json(
        f"{settings.compiler_agent_url}/compile",
        {"draft": session.draft},
    )


async def handle_specialist_text(session: SpecialistSession, text: str) -> str:
    session.language = detect_language(text)
    intent = detect_rule_based_intent(text) or SpecialistIntent.START_OR_CONTINUE_DEFINITION

    if intent in {SpecialistIntent.GREETING, SpecialistIntent.LANGUAGE_SWITCH}:
        return render_greeting(session.language)

    if intent == SpecialistIntent.HELP:
        return render_help(session.language)

    if intent == SpecialistIntent.ASK_WHAT_NEXT:
        return render_what_next(session.language, session.state)

    if intent == SpecialistIntent.RESTART_REQUEST:
        session.state = SpecialistState.IDLE
        session.draft = {}
        session.last_structured_result = None
        session.compiled_graph_id = None
        return (
            "Ок, начинаем заново. Пришли новую идею, шкалу или guideline."
            if session.language == "ru"
            else
            "Okay, let's start from scratch. Send a new idea, scale, or guideline."
        )

    if intent == SpecialistIntent.ASK_SUMMARY:
        if not session.last_structured_result:
            return (
                "Пока у меня нет собранного черновика."
                if session.language == "ru"
                else
                "I do not have a collected draft yet."
            )
        return render_structured_reply(session.language, session.last_structured_result)

    if intent == SpecialistIntent.COMPILE_REQUEST:
        if not session.draft:
            return (
                "Пока нечего компилировать: сначала пришли описание ассессмента или шкалу."
                if session.language == "ru"
                else
                "There is nothing to compile yet: first send the assessment description or scale."
            )

        session.state = SpecialistState.COMPILE_IN_PROGRESS
        try:
            compile_result = await call_compiler_agent(session)
        except Exception:
            session.state = SpecialistState.READY_TO_COMPILE
            return (
                "Во время компиляции произошла ошибка. Попробуй ещё раз позже."
                if session.language == "ru"
                else
                "A compilation error occurred. Please try again later."
            )

        if compile_result.get("status") == "compiled":
            session.state = SpecialistState.COMPILED
            session.compiled_graph_id = compile_result.get("graph_version_id")
            return (
                f"Готово — graph успешно собран.\n\ngraph_version_id: {session.compiled_graph_id}"
                if session.language == "ru"
                else
                f"Done — the graph was compiled successfully.\n\ngraph_version_id: {session.compiled_graph_id}"
            )

        session.state = SpecialistState.CLARIFYING_DEFINITION
        feedback = compile_result.get("feedback", [])
        base = ["Я попробовал собрать graph, но пока есть проблемы:"] if session.language == "ru" else ["I tried to compile the graph, but there are still issues:"]
        for item in feedback:
            base.append(f"- {item}")
        return "\n".join(base)

    if intent == SpecialistIntent.PUBLISH_REQUEST:
        if session.state != SpecialistState.COMPILED:
            return (
                "Publish пока недоступен: сначала нужно успешно собрать graph."
                if session.language == "ru"
                else
                "Publish is not available yet: the graph must be compiled first."
            )
        return (
            "В этом scaffold publish пока не реализован как отдельный шаг, но graph уже собран."
            if session.language == "ru"
            else
            "In this scaffold, publish is not implemented as a separate step yet, but the graph is already compiled."
        )

    try:
        result = await call_definition_agent(session, text)
    except Exception:
        return (
            "Не удалось обновить definition из-за внутренней ошибки. Попробуй ещё раз через несколько секунд."
            if session.language == "ru"
            else
            "I could not update the definition because of an internal error. Please try again in a few seconds."
        )

    session.last_structured_result = result
    session.draft = result.get("draft", {}) or session.draft

    if result.get("status") == "ready_to_compile":
        session.state = SpecialistState.READY_TO_COMPILE
    elif result.get("status") == "needs_clarification":
        session.state = SpecialistState.CLARIFYING_DEFINITION
    else:
        session.state = SpecialistState.COLLECTING_DEFINITION

    return render_structured_reply(session.language, result)


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    session = get_or_create_session(message.chat.id)
    session.language = "ru"
    await message.answer(render_greeting("ru"))


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    session = get_or_create_session(message.chat.id)
    await message.answer(render_help(session.language))


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
