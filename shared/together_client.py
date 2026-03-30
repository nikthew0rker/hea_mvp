from together import AsyncTogether

from shared.config import get_settings


class TogetherAIClient:
    """
    Shared Together AI wrapper.

    This module centralizes:
    - API key usage
    - model selection
    - chat-completions interface

    The rest of the code should not instantiate Together clients directly.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.together_model
        self.client = AsyncTogether(api_key=settings.together_api_key)

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Run one chat completion and return plain text content.

        This keeps the first scaffold simple and consistent across all agents.
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content
