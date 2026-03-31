import asyncio

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from shared.config import get_settings
from shared.http_client import post_json
from shared.published_graph_store import load_active_graph_record

settings = get_settings()
dp = Dispatcher()


def _has_runnable_graph(active: dict | None) -> bool:
    if not isinstance(active, dict):
        return False
    graph = active.get("graph")
    if not isinstance(graph, dict):
        return False

    if isinstance(graph.get("nodes"), list) and graph.get("nodes"):
        return True
    if isinstance(graph.get("questions"), list) and graph.get("questions"):
        return True

    source_draft = graph.get("source_draft", {})
    if isinstance(source_draft, dict):
        questions = source_draft.get("candidate_questions")
        if isinstance(questions, list) and questions:
            return True

    return False


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    active = load_active_graph_record()
    if not _has_runnable_graph(active):
        await message.answer(
            "Сейчас нет опубликованного runnable graph для patient assistant. "
            "Сначала опубликуйте graph из specialist bot."
        )
        return

    conversation_id = f"user_conv_{message.chat.id}"
    try:
        result = await post_json(
            f"{settings.patient_controller_url}/chat",
            {"conversation_id": conversation_id, "user_message": "/start"},
        )
    except httpx.HTTPError:
        await message.answer(
            "Patient controller is temporarily unavailable. Please try again in a moment."
        )
        return

    await message.answer(result["reply_text"])


@dp.message(F.text)
async def user_message_handler(message: Message) -> None:
    active = load_active_graph_record()
    if not _has_runnable_graph(active):
        await message.answer(
            "No runnable published graph is available yet. Please publish a graph from the specialist bot first."
        )
        return

    conversation_id = f"user_conv_{message.chat.id}"

    try:
        result = await post_json(
            f"{settings.patient_controller_url}/chat",
            {"conversation_id": conversation_id, "user_message": message.text},
        )
    except httpx.HTTPError:
        await message.answer(
            "Patient controller is temporarily unavailable. Please try again in a moment."
        )
        return

    await message.answer(result["reply_text"])


async def main() -> None:
    bot = Bot(token=settings.user_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
