from __future__ import annotations

import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hea.bots.user_bot.bot import _looks_like_pdf_request, text_handler  # noqa: E402


class UserBotTests(unittest.TestCase):
    def test_pdf_request_detection(self) -> None:
        self.assertTrue(_looks_like_pdf_request("пдф?"))
        self.assertTrue(_looks_like_pdf_request("send pdf"))
        self.assertFalse(_looks_like_pdf_request("объясни результат"))

    def test_pdf_request_sends_document_to_chat(self) -> None:
        message = SimpleNamespace(
            text="пдф?",
            chat=SimpleNamespace(id=123),
            answer=AsyncMock(),
            answer_document=AsyncMock(),
        )
        with (
            patch("hea.bots.user_bot.bot.post_json", new=AsyncMock(return_value={"reply_text": "Вот ваш отчёт", "state": {"language": "ru"}})),
            patch("hea.bots.user_bot.bot.get_bytes", new=AsyncMock(return_value=(b"%PDF-1.4 test", "application/pdf"))),
        ):
            asyncio.run(text_handler(message))

        message.answer.assert_awaited_once()
        message.answer_document.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
