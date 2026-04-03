from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    together_api_key: str = Field(default="")
    together_model: str = Field(default="Qwen/Qwen3.5-9B")

    specialist_controller_model: str = Field(default="zai-org/GLM-5")
    patient_controller_model: str = Field(default="zai-org/GLM-5")
    definition_agent_model: str = Field(default="Qwen/Qwen3.5-397B-A17B")
    runtime_agent_model: str = Field(default="Qwen/Qwen3.5-9B")
    report_agent_model: str = Field(default="Qwen/Qwen3.5-9B")
    evaluation_agent_model: str = Field(default="Qwen/Qwen3.5-9B")

    specialist_bot_token: str = Field(default="")
    user_bot_token: str = Field(default="")

    definition_agent_url: str = Field(default="http://definition-agent:8000")
    compiler_agent_url: str = Field(default="http://compiler-agent:8000")
    runtime_agent_url: str = Field(default="http://runtime-agent:8000")
    report_agent_url: str = Field(default="http://report-agent:8000")
    evaluation_agent_url: str = Field(default="http://evaluation-agent:8000")
    patient_controller_url: str = Field(default="http://patient-controller:8000")
    specialist_controller_url: str = Field(default="http://specialist-controller:8000")

    langgraph_checkpoint_db_path: str = Field(default="data/langgraph_checkpoints.sqlite")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
