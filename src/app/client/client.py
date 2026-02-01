import os
from langchain_google_genai import ChatGoogleGenerativeAI


# Model tier configuration based on free tier rate limits
# gemini-2.5-flash: 5 RPM (for complex synthesis)
# gemini-2.5-flash-lite: 10 RPM (for lighter analysis)
# gemini-3-flash-preview: 5 RPM (for medium tasks)


class ModelTier:
    """Model tiers for load balancing across free tier limits."""

    FLASH = "gemini-2.5-flash"  # 5 RPM - Complex tasks
    LITE = "gemini-2.5-flash-lite"  # 10 RPM - Lighter tasks
    PREVIEW = "gemini-3-flash-preview"  # 5 RPM - Medium tasks


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
            "GOOGLE_API_KEY not found in environment. " "Please check your .env file."
        )

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
    )


# Pre-configured clients for different node types
# This distributes load across models to maximize throughput


def get_panorama_model():
    """Lighter analysis - uses LITE (10 RPM)."""
    return get_llm_client(ModelTier.LITE, temperature=0.2)


def get_lexical_model():
    """Medium complexity exegesis - uses FLASH (5 RPM)."""
    return get_llm_client(ModelTier.FLASH, temperature=0.1)


def get_historical_model():
    """Medium complexity - uses FLASH (5 RPM)."""
    return get_llm_client(ModelTier.FLASH, temperature=0.2)


def get_intertextual_model():
    """Lighter analysis - uses LITE (10 RPM)."""
    return get_llm_client(ModelTier.LITE, temperature=0.2)


def get_validator_model():
    """Critical validation - uses PREVIEW (5 RPM)."""
    return get_llm_client(ModelTier.PREVIEW, temperature=0.1)


def get_synthesizer_model():
    """Complex synthesis - uses PREVIEW (5 RPM)."""
    return get_llm_client(ModelTier.PREVIEW, temperature=0.4)
