import asyncio

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from shared.config import get_settings
from shared.graph_registry import list_graph_summaries
from shared.http_client import post_json
from shared.published_graph_store import load_active_graph_record

settings = get_settings()
dp = Dispatcher()


def _graph_library_available() -> bool:
    return len(list_graph_summaries(limit=1)) > 0 or isinstance(load_active_graph_record(), dict)


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    if not _graph_library_available():
        await message.answer(
            "Сейчас библиотека assessment graphs пуста. Сначала опубликуйте хотя бы один graph из specialist bot."
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
    if not _graph_library_available():
        await message.answer(
            "There are no published graphs in the library yet. Please publish at least one graph from the specialist bot first."
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
