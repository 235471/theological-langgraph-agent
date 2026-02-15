"""
LLM Client Configuration

3-tier model strategy with fallback chain for deprecation resilience.
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ModelTier:
    """3 primary models — one per load tier for maximum distribution."""

    LITE = "gemini-2.5-flash-lite"  # 10 RPM, 250K TPM, 20 RPD — Light tasks
    FLASH = "gemini-2.5-flash"  # 5 RPM, 250K TPM, 20 RPD — Medium tasks
    TOP = "gemini-3-flash-preview"  # 5 RPM, 250K TPM, 20 RPD — Critical tasks


# Fallback chain: if primary model fails (429 / deprecated), try the next one
MODEL_FALLBACKS = {
    "gemini-3-flash-preview": "gemini-2.5-flash",
    "gemini-2.5-flash": "gemini-2.5-flash-lite",
    "gemini-2.5-flash-lite": "gemini-2.0-flash-lite",  # last resort
}


def get_llm_client(
    model: str = ModelTier.FLASH, temperature: float = 0.3
) -> ChatGoogleGenerativeAI:
    """
    Get a configured LLM client instance.

    Args:
        model: Model name from ModelTier constants
        temperature: Sampling temperature (lower = more deterministic)

    Returns:
        Configured ChatGoogleGenerativeAI instance
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not found in environment. Please check your .env file."
        )

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
    )


def get_llm_client_with_fallback(
    model: str, temperature: float = 0.3
) -> tuple[ChatGoogleGenerativeAI, str]:
    """
    Get an LLM client, with automatic fallback on failure.

    Returns:
        Tuple of (client, actual_model_name) — model_name may differ if fallback was used.
    """
    current_model = model

    while current_model:
        try:
            client = get_llm_client(current_model, temperature)
            return client, current_model
        except Exception as e:
            fallback = MODEL_FALLBACKS.get(current_model)
            if fallback:
                logger.warning(
                    f"Model {current_model} failed, falling back to {fallback}: {e}",
                    extra={
                        "event": "model_fallback",
                        "model": current_model,
                        "fallback": fallback,
                    },
                )
                current_model = fallback
            else:
                raise

    raise ValueError(f"All models exhausted starting from {model}")


# --- Pre-configured clients for each node ---


def get_panorama_model():
    """Light optional analysis — uses FLASH (5 RPM)."""
    return get_llm_client(ModelTier.FLASH, temperature=0.2)


def get_lexical_model():
    """Quality exegesis — uses FLASH (5 RPM)."""
    return get_llm_client(ModelTier.FLASH, temperature=0.1)


def get_historical_model():
    """Historical-theological mapping — uses FLASH (5 RPM)."""
    return get_llm_client(ModelTier.FLASH, temperature=0.2)


def get_intertextual_model():
    """Always runs, needs throughput — uses LITE (10 RPM)."""
    return get_llm_client(ModelTier.LITE, temperature=0.2)


def get_validator_model():
    """Most critical node — uses TOP (gemini-3-flash-preview, 5 RPM)."""
    return get_llm_client(ModelTier.TOP, temperature=0.1)


def get_synthesizer_model():
    """Final output quality — uses TOP (gemini-3-flash-preview, 5 RPM)."""
    return get_llm_client(ModelTier.TOP, temperature=0.4)
