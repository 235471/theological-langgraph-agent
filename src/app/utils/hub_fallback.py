"""
LangSmith Hub Fallback Utility

Primary:  Pull prompt + model config from LangSmith Hub.
          LangSmith handles the Google API key via secrets_from_env=True.

Fallback: If Hub is unavailable, load prompt text + model config from the
          local JSON (prompts_fallback.json). The Google API key is read
          from GOOGLE_API_KEY env var (.env locally / Render secret in prod).
"""

import json
import os
from typing import Any

from langsmith import Client
from langchain_core.messages import SystemMessage, HumanMessage
from app.client.client import get_llm_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Reuse the LangSmith client across calls
_ls_client: Client | None = None

FALLBACK_FILE = os.path.join(
    os.path.dirname(__file__), "fallbacks", "prompts_fallback.json"
)


def _get_ls_client() -> Client:
    global _ls_client
    if _ls_client is None:
        _ls_client = Client()
    return _ls_client


def execute_with_fallback(
    prompt_name: str,
    format_vars: dict,
    structured_schema: Any = None,
    max_tokens: int | None = None,
):
    """
    Execute a LangSmith prompt with a resilient local fallback.

    Hub path:      LangSmith manages GOOGLE_API_KEY via secrets_from_env.
                   format_vars are injected by chain.invoke() natively.

    Fallback path: JSON model_config provides model_name + temperature.
                   GOOGLE_API_KEY comes from env (.env / Render secret).
                   format_vars are substituted manually (safe against curly
                   braces in markdown content like panorama_content).

    Returns:
        Tuple (response, raw_aimessage, model_name_used)
    """
    # ─── PRIMARY: LangSmith Hub ────────────────────────────────────────────────
    try:
        chain = _get_ls_client().pull_prompt(
            prompt_name, include_model=True, secrets_from_env=True
        )

        # Resolve actual model name for governance tracking
        base_model = getattr(chain.last, "bound", chain.last)
        model_name_used = getattr(
            base_model, "model_name", getattr(base_model, "model", "unknown")
        )

        if structured_schema:
            # Recompose: prompt | model.with_structured_output — format_vars injected via invoke()
            executable = chain.first | base_model.with_structured_output(
                structured_schema, include_raw=True
            )
            result = executable.invoke(format_vars)
            parsed = result.get("parsed")
            if parsed is None:
                raise ValueError(
                    f"Structured output parsing returned None for '{prompt_name}'. "
                    "The model may have returned unstructured content. Triggering fallback."
                )
            return parsed, result["raw"], model_name_used
        else:
            # chain = prompt | model; format_vars injected natively via invoke()
            result = chain.invoke(format_vars)
            return result, result, model_name_used

    except Exception as hub_err:
        logger.warning(
            f"LangSmith Hub unavailable for '{prompt_name}'. Switching to local JSON fallback.",
            extra={
                "event": "hub_fallback_triggered",
                "prompt": prompt_name,
                "error": str(hub_err),
            },
        )

    # ─── FALLBACK: Local JSON ─────────────────────────────────────────────────
    try:
        with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
            fallback_data = json.load(f).get(prompt_name)

        if not fallback_data:
            raise ValueError(f"'{prompt_name}' not found in fallback JSON.")

        raw_messages = fallback_data.get("messages", [])
        sys_template = raw_messages[0]["template"] if len(raw_messages) > 0 else ""
        hum_template = raw_messages[1]["template"] if len(raw_messages) > 1 else ""

        # Model config from the JSON (saved from last successful Hub sync)
        model_cfg = fallback_data.get("model_config", {})
        model_name_used = model_cfg.get("model_name", "gemini-2.5-flash")
        temp_used = model_cfg.get("temperature", 0.2)

        # GOOGLE_API_KEY comes from env (.env locally / Render secret in prod)
        model = get_llm_client(
            model=model_name_used,
            temperature=temp_used,
            max_output_tokens=max_tokens,
        )

        # Manually substitute format_vars into the raw template strings.
        # We cannot use ChatPromptTemplate.from_messages() + .invoke(format_vars) here
        # because LangChain calls Python's .format(), which fails when VALUES (e.g.
        # panorama_content) themselves contain curly braces from markdown content.
        sys_content = sys_template
        hum_content = hum_template
        for key, value in format_vars.items():
            placeholder = "{" + key + "}"
            sys_content = sys_content.replace(placeholder, str(value or ""))
            hum_content = hum_content.replace(placeholder, str(value or ""))

        msgs = [SystemMessage(content=sys_content), HumanMessage(content=hum_content)]

        if structured_schema:
            result = model.with_structured_output(
                structured_schema, include_raw=True
            ).invoke(msgs)
            return result["parsed"], result["raw"], f"{model_name_used} [fallback]"
        else:
            result = model.invoke(msgs)
            return result, result, f"{model_name_used} [fallback]"

    except Exception as fallback_err:
        logger.error(f"Fallback also failed for '{prompt_name}': {fallback_err}")
        raise RuntimeError(
            f"Total failure for '{prompt_name}'. "
            f"Hub error: {hub_err} | Fallback error: {fallback_err}"
        )
