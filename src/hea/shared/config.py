from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    together_api_key: str = Field(default="")
    together_model: str = Field(default="openai/gpt-oss-120b")

    # Recommended four-role setup for specialist authoring:
    # 1) controller_model         -> routing / intents / edit planning
    # 2) specialist_compiler_model -> typed questionnaire compilation
    # 3) extraction_model          -> lightweight extraction / noisy text helpers
    # 4) specialist_critic_model   -> consistency review / validation pass
    # 5) fast_model                -> conversational replies / summaries
    controller_model: str = Field(default="MiniMaxAI/MiniMax-M2.5")
    specialist_compiler_model: str = Field(default="zai-org/GLM-5")
    extraction_model: str = Field(default="zai-org/GLM-5")
    specialist_critic_model: str = Field(default="MiniMaxAI/MiniMax-M2.5")
    fast_model: str = Field(default="MiniMaxAI/MiniMax-M2.5")

    specialist_bot_token: str = Field(default="")
    user_bot_token: str = Field(default="")

    specialist_controller_host: str = Field(default="http://localhost:8107")
    patient_controller_host: str = Field(default="http://localhost:8106")
    provider_timeout_seconds: float = Field(default=240.0)
    controller_request_timeout_seconds: float = Field(default=360.0)

    hea_db_path: str = Field(default="data/hea.sqlite")
    log_level: str = Field(default="INFO")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def db_path(self) -> Path:
        path = Path(self.hea_db_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
