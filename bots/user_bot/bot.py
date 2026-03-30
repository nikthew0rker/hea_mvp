import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from shared.config import get_settings
from shared.http_client import post_json

settings = get_settings()
dp = Dispatcher()

ACTIVE_GRAPH_VERSION = "graph_v1_demo"


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    """
    Entry point for the User Bot.

    This bot sends user messages to the Runtime Agent.
    """
    await message.answer(
        "Hi. I am your assessment bot. Tell me how you are doing, and I will guide you through the assessment. "
        "Type 'done' when you want to finish."
    )


@dp.message(F.text)
async def user_message_handler(message: Message) -> None:
    """
    Handle end-user messages.

    The bot:
    - sends user text to the Runtime Agent
    - returns the runtime reply
    - if the session is finished, calls the Report Agent
    """
    conversation_id = f"user_conv_{message.chat.id}"

    runtime_payload = {
        "conversation_id": conversation_id,
        "user_message": message.text,
        "active_graph_version_id": ACTIVE_GRAPH_VERSION,
    }

    runtime_result = await post_json(f"{settings.runtime_agent_url}/message", runtime_payload)
    await message.answer(runtime_result["reply_text"])

    if runtime_result.get("should_generate_report"):
        report_payload = {
            "session_state": runtime_result["session_state"],
            "graph": {"graph_version_id": ACTIVE_GRAPH_VERSION},
        }
        report_result = await post_json(f"{settings.report_agent_url}/generate", report_payload)
        await message.answer(f"Summary:\n{report_result['short_summary']}")


async def main() -> None:
    """
    Bot bootstrap.

    Polling is enough for the MVP scaffold.
    """
    bot = Bot(token=settings.user_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
