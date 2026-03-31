import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from shared.config import get_settings
from shared.http_client import post_json
from shared.published_graph_store import load_active_graph_record

settings = get_settings()
dp = Dispatcher()


def get_active_graph_context() -> dict | None:
    """
    Load the currently published graph record for patient assistant use.
    """
    return load_active_graph_record()


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    """
    Entry point for the User Bot.

    The patient assistant now reads the published active graph instead of using
    a hardcoded demo graph id.
    """
    active = get_active_graph_context()
    if not active:
        await message.answer(
            "Сейчас нет опубликованного графа для patient assistant. "
            "Сначала опубликуйте граф из specialist bot."
        )
        return

    graph_id = active.get("graph_id")
    await message.answer(
        f"Hi. I am your assessment bot. Active graph: {graph_id}. "
        f"Tell me how you are doing, and I will guide you through the assessment. "
        f"Type 'done' when you want to finish."
    )


@dp.message(F.text)
async def user_message_handler(message: Message) -> None:
    """
    Handle end-user messages.

    The bot:
    - loads the currently published active graph
    - sends the user message to the Runtime Agent
    - if the session is finished, calls the Report Agent with the active graph payload
    """
    active = get_active_graph_context()
    if not active:
        await message.answer(
            "No published graph is available yet. Please publish a graph from the specialist bot first."
        )
        return

    graph_id = active.get("graph_id", "unknown_graph")
    graph_payload = active.get("graph", {"graph_version_id": graph_id})

    conversation_id = f"user_conv_{message.chat.id}"

    runtime_payload = {
        "conversation_id": conversation_id,
        "user_message": message.text,
        "active_graph_version_id": graph_id,
    }

    runtime_result = await post_json(f"{settings.runtime_agent_url}/message", runtime_payload)
    await message.answer(runtime_result["reply_text"])

    if runtime_result.get("should_generate_report"):
        report_payload = {
            "session_state": runtime_result["session_state"],
            "graph": graph_payload,
        }
        report_result = await post_json(f"{settings.report_agent_url}/generate", report_payload)
        await message.answer(f"Summary:\n{report_result['short_summary']}")


async def main() -> None:
    """
    Bot bootstrap.
    """
    bot = Bot(token=settings.user_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
