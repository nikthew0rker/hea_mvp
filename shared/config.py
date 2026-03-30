from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Shared project settings.

    The purpose of this module is to keep all environment-based configuration
    in one place and avoid hardcoding tokens or service URLs in code.
    """

    together_api_key: str = Field(default="")
    together_model: str = Field(default="meta-llama/Llama-4-Scout-17B-16E-Instruct")

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
    Return one cached Settings instance for the process.
    """
    return Settings()
