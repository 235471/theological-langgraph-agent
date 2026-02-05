from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from app.agent.agentState import TheologicalState
from app.utils.prompts import (
    PANORAMA_PROMPT,
    LEXICAL_EXEGESIS_PROMPT,
    HISTORICAL_THEOLOGICAL_PROMPT,
    INTERTEXTUALITY_PROMPT,
    THEOLOGICAL_VALIDATOR_PROMPT,
    SYNTHETIZER_PROMPT,
)
from app.client.client import (
    get_panorama_model,
    get_lexical_model,
    get_historical_model,
    get_intertextual_model,
    get_validator_model,
    get_synthesizer_model,
)
from app.agent.model import AnalysisOutput


def sanitize_llm_output(content: str) -> str:
    """
    Sanitizes LLM output to ensure proper markdown formatting.

    Fixes:
    - Escaped newlines (\\n) -> actual newlines
    - Accidental JSON wrapper structures
    """
    # Fix escaped newlines
    if "\\n" in content:
        content = content.replace("\\n", "\n")

    # Remove JSON wrapper if accidentally present
    if content.strip().startswith("{") and '"content":' in content:
        import json

        try:
            parsed = json.loads(content)
            content = parsed.get("content", content)
        except:
            pass  # If parsing fails, keep original

    return content


def build_graph():
    builder = StateGraph(TheologicalState)

    # 1. Add nodes (remove router from nodes, it's just a function)
    builder.add_node("panorama_agent", panorama_node)
    builder.add_node("lexical_agent", lexical_node)
    builder.add_node("historical_agent", historical_node)
    builder.add_node("intertextual_agent", intertextual_node)
    builder.add_node("join", join_node)
    builder.add_node("theological_validator", theological_validator_node)
    builder.add_node("synthesizer", synthesizer_node)

    # 2. Set entry point to the router function
    builder.set_conditional_entry_point(router_function)

    # 3. Convergence (Gather) - all agents go to join
    builder.add_edge("panorama_agent", "join")
    builder.add_edge("lexical_agent", "join")
    builder.add_edge("historical_agent", "join")
    builder.add_edge("intertextual_agent", "join")

    # 4. Continue to the next node
    builder.add_edge("join", "theological_validator")

    # 5. Final Synthesis
    builder.add_edge("theological_validator", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()


def router_function(state: TheologicalState):
    """
    Router function that determines which agents to run.
    Returns a list of Send objects for dynamic fan-out.
    """
    sends = [Send("intertextual_agent", state)]  # Always run intertextual

    if "panorama" in state["selected_modules"]:
        sends.append(Send("panorama_agent", state))

    if "exegese" in state["selected_modules"]:
        sends.append(Send("lexical_agent", state))

    if "historical" in state["selected_modules"]:
        sends.append(Send("historical_agent", state))

    return sends


def panorama_node(state: TheologicalState):
    """Panorama analysis using LITE model (10 RPM)."""
    model = get_panorama_model()
    system_prompt = PANORAMA_PROMPT.format(
        livro=state["bible_book"],
        capitulo=state["chapter"],
        versiculos=" ".join(state["verses"]),
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Execute panorama analysis"),
    ]
    llm_with_structure = model.with_structured_output(AnalysisOutput)
    response = llm_with_structure.invoke(messages)
    return {"panorama_content": sanitize_llm_output(response.content)}


def lexical_node(state: TheologicalState):
    """Lexical exegesis using FLASH model (5 RPM)."""
    model = get_lexical_model()
    system_prompt = LEXICAL_EXEGESIS_PROMPT.format(
        livro=state["bible_book"],
        capitulo=state["chapter"],
        versiculos=" ".join(state["verses"]),
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Execute exegesis analysis"),
    ]
    llm_with_structure = model.with_structured_output(AnalysisOutput)
    response = llm_with_structure.invoke(messages)
    return {"lexical_content": sanitize_llm_output(response.content)}


def historical_node(state: TheologicalState):
    """Historical-theological analysis using FLASH model (5 RPM)."""
    model = get_historical_model()
    system_prompt = HISTORICAL_THEOLOGICAL_PROMPT.format(
        livro=state["bible_book"],
        capitulo=state["chapter"],
        versiculos=" ".join(state["verses"]),
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Execute the historical theological analysis"),
    ]
    llm_with_structure = model.with_structured_output(AnalysisOutput)
    response = llm_with_structure.invoke(messages)
    return {"historical_content": sanitize_llm_output(response.content)}


def intertextual_node(state: TheologicalState):
    """Intertextuality analysis using LITE model (10 RPM)."""
    model = get_intertextual_model()
    system_prompt = INTERTEXTUALITY_PROMPT.format(
        livro=state["bible_book"],
        capitulo=state["chapter"],
        versiculos=" ".join(state["verses"]),
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Execute intertextuality analysis"),
    ]
    llm_with_structure = model.with_structured_output(AnalysisOutput)
    response = llm_with_structure.invoke(messages)
    return {"intertextual_content": sanitize_llm_output(response.content)}


def theological_validator_node(state: TheologicalState):
    """Theological validation using PREVIEW model (5 RPM) - critical task."""
    model = get_validator_model()
    sections = []

    if state.get("panorama_content"):
        sections.append(f"Panorama:\n{state['panorama_content']}")

    if state.get("lexical_content"):
        sections.append(f"Exegese:\n{state['lexical_content']}")

    if state.get("historical_content"):
        sections.append(f"Teologia Histórica:\n{state['historical_content']}")

    sections.append(f"Intertextualidade:\n{state['intertextual_content']}")

    user_prompt = "\n\n".join(sections)

    messages = [
        SystemMessage(content=THEOLOGICAL_VALIDATOR_PROMPT),
        HumanMessage(content=user_prompt),
    ]
    llm_with_structure = model.with_structured_output(AnalysisOutput)
    response = llm_with_structure.invoke(messages)
    return {"validation_content": sanitize_llm_output(response.content)}


def synthesizer_node(state: TheologicalState):
    """Final synthesis using PREVIEW model (5 RPM) - complex generation."""
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
    llm_with_structure = model.with_structured_output(AnalysisOutput)
    response = llm_with_structure.invoke(messages)
    return {"final_analysis": sanitize_llm_output(response.content)}


def join_node(state: TheologicalState):
    """Synchronization point - passthrough node that waits for all branches."""
    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        f"Join node called. Current contents: panorama={bool(state.get('panorama_content'))}, "
        f"lexical={bool(state.get('lexical_content'))}, "
        f"historical={bool(state.get('historical_content'))}, "
        f"intertextual={bool(state.get('intertextual_content'))}"
    )
    return {}
