import json
import re
from typing import Any

from together import AsyncTogether

from shared.config import get_settings


class TogetherAIClient:
    """
    Shared Together AI client wrapper.

    Supports:
    - per-call model selection
    - plain text completion
    - tolerant JSON extraction from model output
    """

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.together_model
        self.client = AsyncTogether(api_key=settings.together_api_key)

    async def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        """
        Run one chat completion and return plain text content.
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
        """
        Ask the model for JSON and recover one JSON object from its output.
        """
        raw = await self.complete_text(system_prompt, user_prompt)
        return self._extract_json_object(raw)

    @staticmethod
    def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
        """
        Recover a JSON object from free-form text.
        """
        if not raw_text or not isinstance(raw_text, str):
            return None

        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            obj = json.loads(cleaned)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None

        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None

        return None
