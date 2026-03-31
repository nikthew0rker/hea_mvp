from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Shared project settings.

    The specialist-side stack now uses:
    - specialist_controller_model for controller reasoning
    - definition_agent_model for structured extraction and edit application
    """

    together_api_key: str = Field(default="")
    together_model: str = Field(default="Qwen/Qwen3.5-9B")

    specialist_controller_model: str = Field(default="zai-org/GLM-5")
    definition_agent_model: str = Field(default="Qwen/Qwen3.5-397B-A17B")
    runtime_agent_model: str = Field(default="Qwen/Qwen3.5-9B")
    report_agent_model: str = Field(default="Qwen/Qwen3.5-9B")
    evaluation_agent_model: str = Field(default="Qwen/Qwen3.5-9B")

    specialist_bot_token: str = Field(default="")
    user_bot_token: str = Field(default="")

    definition_agent_url: str = Field(default="http://127.0.0.1:8101")
    compiler_agent_url: str = Field(default="http://127.0.0.1:8102")
    runtime_agent_url: str = Field(default="http://127.0.0.1:8103")
    report_agent_url: str = Field(default="http://127.0.0.1:8104")
    evaluation_agent_url: str = Field(default="http://127.0.0.1:8105")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return one cached Settings instance.
    """
    return Settings()
