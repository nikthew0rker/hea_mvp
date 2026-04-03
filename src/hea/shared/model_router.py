from __future__ import annotations

import logging

from hea.shared.config import get_settings
from hea.shared.together_client import TogetherAIClient

logger = logging.getLogger(__name__)


JSON_CRITICAL_ROLE_CONFIG = {
    "controller_model": "controller",
    "specialist_compiler_model": "specialist_compiler",
    "extraction_model": "extraction",
    "specialist_critic_model": "specialist_critic",
}


def controller_client() -> TogetherAIClient:
    settings = get_settings()
    return TogetherAIClient(model=settings.controller_model)


def extraction_client() -> TogetherAIClient:
    settings = get_settings()
    return TogetherAIClient(model=settings.extraction_model)


def specialist_compiler_client() -> TogetherAIClient:
    settings = get_settings()
    return TogetherAIClient(model=settings.specialist_compiler_model)


def specialist_critic_client() -> TogetherAIClient:
    settings = get_settings()
    return TogetherAIClient(model=settings.specialist_critic_model)


def fast_client() -> TogetherAIClient:
    settings = get_settings()
    return TogetherAIClient(model=settings.fast_model)


def log_model_configuration_warnings() -> None:
    settings = get_settings()
    unsafe = TogetherAIClient.JSON_UNSAFE_MODELS
    for field_name, role_name in JSON_CRITICAL_ROLE_CONFIG.items():
        configured_model = getattr(settings, field_name)
        if configured_model in unsafe:
            logger.warning(
                "JSON-unsafe Together model configured for %s role: %s. "
                "Structured calls will be auto-rerouted to a safer model.",
                role_name,
                configured_model,
            )


MODEL_MAP = {
    # specialist
    "specialist_route_intent": "controller_model",
    "specialist_compile_questionnaire": "specialist_compiler_model",
    "specialist_extract_from_noisy_text": "extraction_model",
    "specialist_critic_review": "specialist_critic_model",
    "specialist_render_reply": "fast_model",
    # patient
    "patient_route_intent": "controller_model",
    "patient_graph_match_disambiguation": "controller_model",
    "patient_runtime_fallback": "fast_model",
    "patient_explain_result": "fast_model",
    "patient_report": "fast_model",
}
