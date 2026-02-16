"""
LangGraph Agent Builder

Multi-agent theological analysis system with:
- Fan-out/fan-in parallel execution
- Governance metadata capture (tokens, model, duration)
- HITL conditional edge on theological validator
- Structured logging with run_id correlation
"""

import time
from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.types import Send

from app.agent.agentState import TheologicalState
from app.agent.model import AnalysisOutput, ValidatorOutput
from app.utils.prompts import (
    PANORAMA_PROMPT,
    LEXICAL_EXEGESIS_PROMPT,
    HISTORICAL_THEOLOGICAL_PROMPT,
    INTERTEXTUALITY_PROMPT,
    THEOLOGICAL_VALIDATOR_PROMPT,
    SYNTHETIZER_PROMPT,
)
from app.client.client import (
    ModelTier,
    get_panorama_model,
    get_lexical_model,
    get_historical_model,
    get_intertextual_model,
    get_validator_model,
    get_synthesizer_model,
)
from app.service.hitl_service import save_pending_review
from app.service.email_service import send_hitl_notification
from app.utils.logger import get_logger

logger = get_logger(__name__)


# --- Helpers ---


def sanitize_llm_output(content: str) -> str:
    """
    Sanitizes LLM output to ensure proper markdown formatting.

    Fixes:
    - Escaped newlines (\\n) -> actual newlines
    - Accidental JSON wrapper structures
    """
    if "\\n" in content:
        content = content.replace("\\n", "\n")

    if content.strip().startswith("{") and '"content":' in content:
        import json

        try:
            parsed = json.loads(content)
            content = parsed.get("content", content)
        except Exception:
            pass

    return content


def extract_token_usage(response) -> dict:
    """Extract token usage from LLM response metadata (zero cost)."""
    usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        meta = response.usage_metadata
        usage = {
            "input": (
                getattr(meta, "input_tokens", 0) or meta.get("input_tokens", 0)
                if isinstance(meta, dict)
                else getattr(meta, "input_tokens", 0)
            ),
            "output": (
                getattr(meta, "output_tokens", 0) or meta.get("output_tokens", 0)
                if isinstance(meta, dict)
                else getattr(meta, "output_tokens", 0)
            ),
        }
    elif hasattr(response, "response_metadata"):
        meta = response.response_metadata or {}
        token_usage = meta.get("token_usage") or meta.get("usage_metadata") or {}
        if isinstance(token_usage, dict):
            usage = {
                "input": token_usage.get(
                    "input_tokens", token_usage.get("prompt_tokens", 0)
                ),
                "output": token_usage.get(
                    "output_tokens", token_usage.get("completion_tokens", 0)
                ),
            }
    return usage


def _build_node_result(
    state: TheologicalState,
    node_name: str,
    model_name: str,
    response,
    start_time: float,
    output_field: str,
    raw_response=None,
    extra_fields: dict | None = None,
    extra_reasoning: dict | None = None,
) -> dict:
    """
    Build the standard governance return dict for any node.

    Encapsulates the DRY pattern shared by all analysis nodes:
    - Sanitize LLM output
    - Extract token usage
    - Log completion
    - Merge model version, token usage, and reasoning step

    Args:
        state: Current graph state
        node_name: Node identifier (e.g. 'panorama_agent')
        model_name: Model tier used (e.g. ModelTier.FLASH)
        response: Parsed structured response (has .content)
        start_time: time.time() captured at node start
        output_field: State key to write content to (e.g. 'panorama_content')
        raw_response: Optional raw AIMessage for token extraction
        extra_fields: Optional dict merged into the return (e.g. {'risk_level': 'high'})
        extra_reasoning: Optional dict merged into the reasoning step (e.g. {'alerts': [...]})

    Returns:
        Dict ready to be returned from the node function.
    """
    duration_ms = int((time.time() - start_time) * 1000)
    # Extract tokens from raw AIMessage (has usage_metadata), not from parsed Pydantic model
    usage = (
        extract_token_usage(raw_response)
        if raw_response
        else extract_token_usage(response)
    )

    # Structured log
    log_extra = {
        "event": "node_complete",
        "node": node_name,
        "model": model_name,
        "tokens": usage,
        "duration_ms": duration_ms,
        "run_id": state.get("run_id"),
    }
    if extra_reasoning:
        log_extra.update(extra_reasoning)
    logger.info(f"{node_name} completed", extra=log_extra)

    # Reasoning step payload
    reasoning_entry = {
        "node": node_name,
        "model": model_name,
        "tokens": usage,
        "duration_ms": duration_ms,
    }
    if extra_reasoning:
        reasoning_entry.update(extra_reasoning)

    # Immutable state — reducers in TheologicalState handle merging
    result = {
        output_field: sanitize_llm_output(response.content),
        "model_versions": {node_name: model_name},
        "tokens_consumed": {node_name: usage},
        "reasoning_steps": [reasoning_entry],
    }

    if extra_fields:
        result.update(extra_fields)

    return result


# --- Graph Builder ---


def build_graph():
    builder = StateGraph(TheologicalState)

    # 1. Add nodes
    builder.add_node("panorama_agent", panorama_node)
    builder.add_node("lexical_agent", lexical_node)
    builder.add_node("historical_agent", historical_node)
    builder.add_node("intertextual_agent", intertextual_node)
    builder.add_node("join", join_node)
    builder.add_node("theological_validator", theological_validator_node)
    builder.add_node("hitl_pending", hitl_pending_node)
    builder.add_node("synthesizer", synthesizer_node)

    # 2. Entry point: dynamic fan-out via router
    builder.set_conditional_entry_point(router_function)

    # 3. Convergence — all analysis agents go to join
    builder.add_edge("panorama_agent", "join")
    builder.add_edge("lexical_agent", "join")
    builder.add_edge("historical_agent", "join")
    builder.add_edge("intertextual_agent", "join")

    # 4. Join → Validator
    builder.add_edge("join", "theological_validator")

    # 5. Conditional edge: validator decides if HITL is needed
    builder.add_conditional_edges(
        "theological_validator",
        route_after_validation,
        {
            "hitl_pending": "hitl_pending",
            "synthesizer": "synthesizer",
        },
    )

    # 6. HITL pending → END (halts execution, awaits human review)
    builder.add_edge("hitl_pending", END)

    # 7. Synthesizer → END
    builder.add_edge("synthesizer", END)

    return builder.compile()


# --- Router ---


def router_function(state: TheologicalState):
    """
    Router function that determines which agents to run.
    Returns a list of Send objects for dynamic fan-out.
    """
    sends = [Send("intertextual_agent", state)]  # Always run intertextual

    selected = []
    if "panorama" in state["selected_modules"]:
        sends.append(Send("panorama_agent", state))
        selected.append("panorama")

    if "exegese" in state["selected_modules"]:
        sends.append(Send("lexical_agent", state))
        selected.append("exegese")

    if "historical" in state["selected_modules"]:
        sends.append(Send("historical_agent", state))
        selected.append("historical")

    selected.append("intertextual")

    logger.info(
        f"Router: selected modules = {selected}",
        extra={"event": "router", "run_id": state.get("run_id"), "node": "router"},
    )

    return sends


# --- Conditional Edge: after Validation ---


def route_after_validation(state: TheologicalState) -> str:
    """Route to HITL pending or synthesizer based on risk level."""
    risk = state.get("risk_level", "low")
    if risk == "high":
        logger.warning(
            "High risk detected — routing to HITL",
            extra={
                "event": "hitl_trigger",
                "run_id": state.get("run_id"),
                "risk_level": risk,
            },
        )
        return "hitl_pending"
    return "synthesizer"


# --- Analysis Nodes ---


def panorama_node(state: TheologicalState):
    """Panorama analysis — FLASH model (gemini-2.5-flash, 5 RPM)."""
    start = time.time()
    model = get_panorama_model()

    system_prompt = PANORAMA_PROMPT.format(
        livro=state["bible_book"],
        capitulo=state["chapter"],
        versiculos=" ".join(state["verses"]),
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Analise a passagem conforme o contexto canônico."),
    ]
    response = model.invoke(messages)

    return _build_node_result(
        state,
        "panorama_agent",
        ModelTier.LITE,
        response,
        start,
        output_field="panorama_content",
        raw_response=response,
    )


def lexical_node(state: TheologicalState):
    """Lexical exegesis — FLASH model (gemini-2.5-flash, 5 RPM)."""
    start = time.time()
    model = get_lexical_model()

    book = state["bible_book"]
    chapter = state["chapter"]
    verses_str = " ".join(state["verses"])

    system_prompt = LEXICAL_EXEGESIS_PROMPT.format(
        livro=book,
        capitulo=chapter,
        versiculos=verses_str,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Realize a exegese lexical dos principais termos."),
    ]
    response = model.invoke(messages)

    return _build_node_result(
        state,
        "lexical_agent",
        ModelTier.FAST,
        response,
        start,
        output_field="lexical_content",
        raw_response=response,
    )


def historical_node(state: TheologicalState):
    """Historical-theological analysis — FLASH model (gemini-2.5-flash, 5 RPM)."""
    start = time.time()
    model = get_historical_model()

    book = state["bible_book"]
    chapter = state["chapter"]
    verses_str = " ".join(state["verses"])

    system_prompt = HISTORICAL_THEOLOGICAL_PROMPT.format(
        livro=book,
        capitulo=chapter,
        versiculos=verses_str,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Mapeie as interpretações históricas e teológicas."),
    ]
    response = model.invoke(messages)

    return _build_node_result(
        state,
        "historical_agent",
        ModelTier.FAST,
        response,
        start,
        output_field="historical_content",
        raw_response=response,
    )


def intertextual_node(state: TheologicalState):
    """Intertextuality analysis — LITE model (gemini-2.5-flash-lite, 10 RPM)."""
    start = time.time()
    model = get_intertextual_model()

    book = state["bible_book"]
    chapter = state["chapter"]
    verses_str = " ".join(state["verses"])

    system_prompt = INTERTEXTUALITY_PROMPT.format(
        livro=book,
        capitulo=chapter,
        versiculos=verses_str,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Identifique e analise as conexões intertextuais."),
    ]
    response = model.invoke(messages)

    return _build_node_result(
        state,
        "intertextual_agent",
        ModelTier.LITE,
        response,
        start,
        output_field="intertextual_content",
        raw_response=response,
    )


# --- Validator Node (with HITL risk assessment) ---


def theological_validator_node(state: TheologicalState):
    """
    Theological validation — TOP model (gemini-3-flash-preview, 5 RPM).
    Uses ValidatorOutput to extract risk_level and alerts for HITL decisions.
    """
    start = time.time()
    model = get_validator_model()

    system_prompt = THEOLOGICAL_VALIDATOR_PROMPT.format(
        panorama_content=state.get("panorama_content") or "",
        lexical_content=state.get("lexical_content") or "",
        historical_content=state.get("historical_content") or "",
        intertextual_content=state.get("intertextual_content") or "",
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Validate the theological reports."),
    ]
    result = model.with_structured_output(ValidatorOutput, include_raw=True).invoke(
        messages
    )
    response = result["parsed"]
    raw = result["raw"]

    risk_level = getattr(response, "risk_level", "low")
    alerts = getattr(response, "alerts", [])

    return _build_node_result(
        state,
        "theological_validator",
        ModelTier.TOP,
        response,
        start,
        output_field="validation_content",
        raw_response=raw,
        extra_fields={"risk_level": risk_level},
        extra_reasoning={"risk_level": risk_level, "alerts": alerts},
    )


# --- HITL Pending Node ---


def hitl_pending_node(state: TheologicalState):
    """
    Halts execution and persists state for human review.
    Sends email notification to the reviewer.
    """
    run_id = state.get("run_id", "unknown")
    verses_int = [int(v) for v in state.get("verses", [])]

    # Persist to hitl_reviews table
    try:
        save_pending_review(
            run_id=run_id,
            book=state["bible_book"],
            chapter=state["chapter"],
            verses=verses_int,
            risk_level=state.get("risk_level", "high"),
            alerts=state.get("reasoning_steps", [{}])[-1].get("alerts", []),
            validation_content=state.get("validation_content", ""),
            selected_modules=state.get("selected_modules", []),
            panorama_content=state.get("panorama_content"),
            lexical_content=state.get("lexical_content"),
            historical_content=state.get("historical_content"),
            intertextual_content=state.get("intertextual_content"),
            model_versions=state.get("model_versions"),
            tokens_consumed=state.get("tokens_consumed"),
            reasoning_steps=state.get("reasoning_steps"),
        )
    except Exception as e:
        logger.error(f"Failed to persist HITL state: {e}", extra={"run_id": run_id})

    # Send email notification
    last_step = (state.get("reasoning_steps") or [{}])[-1]
    alerts = last_step.get("alerts", [])

    send_hitl_notification(
        run_id=run_id,
        book=state["bible_book"],
        chapter=state["chapter"],
        verses=verses_int,
        risk_level=state.get("risk_level", "high"),
        alerts=alerts,
    )

    logger.warning(
        f"HITL pending — execution halted for review",
        extra={"event": "hitl_pending", "run_id": run_id},
    )

    return {"hitl_status": "pending"}


# --- Synthesizer Node ---


def synthesizer_node(state: TheologicalState):
    """Final synthesis — TOP model (gemini-3-flash-preview, 5 RPM)."""
    start = time.time()
    model = get_synthesizer_model()

    system_prompt = SYNTHETIZER_PROMPT.format(
        panorama_content=state.get("panorama_content") or "",
        lexical_content=state.get("lexical_content") or "",
        historical_content=state.get("historical_content") or "",
        intertextual_content=state.get("intertextual_content") or "",
        validation_content=state.get("validation_content") or "",
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content="Write the study based on the reports provided, in Brazilian Portuguese"
        ),
    ]
    result = model.with_structured_output(AnalysisOutput, include_raw=True).invoke(
        messages
    )
    response = result["parsed"]
    raw = result["raw"]

    return _build_node_result(
        state,
        "synthesizer",
        ModelTier.TOP,
        response,
        start,
        output_field="final_analysis",
        raw_response=raw,
    )


# --- Join Node ---


def join_node(state: TheologicalState):
    """Synchronization point — passthrough node that waits for all branches."""
    logger.info(
        f"Join node — all branches converged",
        extra={
            "event": "join",
            "run_id": state.get("run_id"),
            "panorama": bool(state.get("panorama_content")),
            "lexical": bool(state.get("lexical_content")),
            "historical": bool(state.get("historical_content")),
            "intertextual": bool(state.get("intertextual_content")),
        },
    )
    return {}
