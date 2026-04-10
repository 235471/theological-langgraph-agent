"""
LLM Client Configuration

3-tier model strategy with fallback chain for deprecation resilience.
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_llm_client(
    model: str = "gemini-3.1-flash-lite-preview",
    temperature: float = 0.3,
    max_output_tokens: int | None = None,
) -> ChatGoogleGenerativeAI:
    """
    Get a configured LLM client instance.

    Args:
        model: Model name string (e.g. "gemini-3.1-flash-lite-preview")
        temperature: Sampling temperature (lower = more deterministic)
        max_output_tokens: Optional cap on generated tokens (prevents hallucination loops)

    Returns:
        Configured ChatGoogleGenerativeAI instance
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not found in environment. Please check your .env file."
        )

    kwargs = {
        "model": model,
        "temperature": temperature,
        "api_key": api_key,
    }
    if max_output_tokens is not None:
        kwargs["max_output_tokens"] = max_output_tokens

    return ChatGoogleGenerativeAI(**kwargs)

