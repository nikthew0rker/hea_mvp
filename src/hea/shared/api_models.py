from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class ChatRequest(BaseModel):
    conversation_id: str = Field(default="unknown")
    user_message: str = Field(default="")
    language: str = Field(default="")

    model_config = ConfigDict(extra="ignore")


class SpecialistChatResponse(BaseModel):
    reply_text: str
    state: dict[str, Any]


class PatientChatResponse(BaseModel):
    status: str
    reply_text: str
    state: dict[str, Any]
