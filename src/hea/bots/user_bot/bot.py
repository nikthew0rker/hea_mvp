import asyncio

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, Message

from hea.shared.config import get_settings
from hea.shared.http import get_bytes, post_json

settings = get_settings()
dp = Dispatcher()


def _looks_like_pdf_request(text: str | None) -> bool:
    low = " ".join(str(text or "").lower().strip().split())
    return any(token in low for token in ["pdf", "пдф", "отправь pdf", "send pdf", "скачай отчет", "скачай отчёт"])


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    conversation_id = f"user_conv_{message.chat.id}"
    try:
        result = await post_json(
            f"{settings.patient_controller_host}/chat",
            {"conversation_id": conversation_id, "user_message": "/start"},
        )
    except httpx.HTTPError:
        await message.answer("Patient controller is temporarily unavailable.")
        return

    await message.answer(result.get("reply_text", ""))


@dp.message(F.text)
async def text_handler(message: Message) -> None:
    conversation_id = f"user_conv_{message.chat.id}"
    try:
        result = await post_json(
            f"{settings.patient_controller_host}/chat",
            {"conversation_id": conversation_id, "user_message": message.text},
        )
    except httpx.HTTPError:
        await message.answer("Patient controller is temporarily unavailable.")
        return

    await message.answer(result.get("reply_text", ""))
    if _looks_like_pdf_request(message.text):
        try:
            pdf_bytes, content_type = await get_bytes(f"{settings.patient_controller_host}/report/{conversation_id}.pdf")
        except httpx.HTTPError:
            return
        if "application/pdf" not in content_type.lower():
            return
        await message.answer_document(
            BufferedInputFile(pdf_bytes, filename=f"{conversation_id}.pdf"),
            caption="PDF report" if (result.get("state", {}) or {}).get("language") == "en" else "PDF-отчёт",
        )


async def main() -> None:
    bot = Bot(token=settings.user_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
