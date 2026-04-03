import asyncio

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from hea.shared.config import get_settings
from hea.shared.http import post_json

settings = get_settings()
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    conversation_id = f"specialist_conv_{message.chat.id}"
    try:
        result = await post_json(
            f"{settings.specialist_controller_host}/chat",
            {"conversation_id": conversation_id, "user_message": "/start"},
        )
    except httpx.HTTPError:
        await message.answer("Specialist controller is temporarily unavailable.")
        return

    await message.answer(result.get("reply_text", ""))


@dp.message(F.text)
async def text_handler(message: Message) -> None:
    conversation_id = f"specialist_conv_{message.chat.id}"
    try:
        result = await post_json(
            f"{settings.specialist_controller_host}/chat",
            {"conversation_id": conversation_id, "user_message": message.text},
        )
    except httpx.HTTPError:
        await message.answer("Specialist controller is temporarily unavailable.")
        return

    await message.answer(result.get("reply_text", ""))


async def main() -> None:
    bot = Bot(token=settings.specialist_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
