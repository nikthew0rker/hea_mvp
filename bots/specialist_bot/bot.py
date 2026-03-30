import asyncio
from uuid import uuid4

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from shared.config import get_settings
from shared.http_client import post_json

settings = get_settings()
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    """
    Entry point for the Specialist Bot.

    This bot collects free-form specialist input and sends it to
    the Definition Agent for draft structuring.
    """
    await message.answer(
        "Hi. Send me a free-form assessment description, and I will turn it into a draft."
    )


@dp.message(F.text)
async def specialist_message_handler(message: Message) -> None:
    """
    Handle specialist text messages.

    For the MVP scaffold:
    - create a new conversation id per message
    - send text to the Definition Agent
    - return draft status and clarification question
    """
    payload = {
        "specialist_text": message.text,
        "conversation_id": f"conv_{uuid4().hex}",
    }

    result = await post_json(f"{settings.definition_agent_url}/draft", payload)

    reply = [
        f"Draft status: {result['draft_status']}",
        "",
        "Stored draft preview:",
        str(result["draft"]),
    ]

    if result.get("clarification_question"):
        reply.extend(["", f"Clarification: {result['clarification_question']}"])

    await message.answer("\n".join(reply))


async def main() -> None:
    """
    Bot bootstrap.

    Polling is enough for the MVP scaffold.
    """
    bot = Bot(token=settings.specialist_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
