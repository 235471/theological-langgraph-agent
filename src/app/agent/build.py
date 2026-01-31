from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from app.agent.agentState import TheologicalState
from app.utils.prompts import (
    PANORAMA_PROMPT,
    LEXICAL_EXEGESIS_PROMPT,
    HISTORICAL_THEOLOGICAL_PROMPT,
    INTERTEXTUALITY_PROMPT,
    THEOLOGICAL_VALIDATOR_PROMPT,
    SYNTHETIZER_PROMPT,
)


def build_graph():
    builder = StateGraph(TheologicalState)

    # 1. Add nodes
    builder.add_node("router", router_node)
    builder.add_node("panorama_agent", panorama_node)
    builder.add_node("lexical_agent", lexical_node)
    builder.add_node("historical_agent", historical_node)
    builder.add_node("intertextual_agent", intertextual_node)
    builder.add_node("join", join_node)
    builder.add_node("theological_validator", theological_validator_node)
    builder.add_node("synthesizer", synthesizer_node)

    # 2. Set entry point
    builder.set_entry_point("router")

    # 3. Conditional Routing (Scatter)
    # The router determines which agents to run based on 'selected_modules'
    builder.add_conditional_edges(
        "router",
        lambda state: router_node(state),  # Logic helper
        # Mapping not strictly needed if names match, but good practice:
        {
            "panorama_agent": "panorama_agent",
            "lexical_agent": "lexical_agent",
            "historical_agent": "historical_agent",
            "intertextual_agent": "intertextual_agent",
        },
    )

    # 4. Convergence (Gather)
    builder.add_edge("panorama_agent", "join")
    builder.add_edge("lexical_agent", "join")
    builder.add_edge("historical_agent", "join")
    builder.add_edge("intertextual_agent", "join")

    # 5. Conditional Proceed (Wait for all)
    # After join, we check: Are we done?
    # If yes -> Validator. If no -> END (this branch finishes, waiting for others)
    builder.add_conditional_edges("join", should_continue)

    # 6. Final Synthesis
    builder.add_edge("theological_validator", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()


def router_node(state: TheologicalState):
    routes = ["intertextual_agent"]

    if "panorama" in state["selected_modules"]:
        routes.append("panorama_agent")

    if "exegese" in state["selected_modules"]:
        routes.append("lexical_agent")

    if "historical" in state["selected_modules"]:
        routes.append("historical_agent")

    return routes


def panorama_node(state: TheologicalState):
    system_prompt = PANORAMA_PROMPT.format(
        livro=state["bible_book"],
        capitulo=state["chapter"],
        versiculos=" ".join(state["verses"]),
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Execute panorama analysis"),
    ]
    response = model.invoke(messages)
    return {"panorama_content": response.content}


def lexical_node(state: TheologicalState):
    system_prompt = LEXICAL_EXEGESIS_PROMPT.format(
        livro=state["bible_book"],
        capitulo=state["chapter"],
        versiculos=" ".join(state["verses"]),
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Execute exegesis analysis"),
    ]
    response = model.invoke(messages)
    return {"lexical_content": response.content}


def historical_node(state: TheologicalState):
    system_prompt = HISTORICAL_THEOLOGICAL_PROMPT.format(
        livro=state["bible_book"],
        capitulo=state["chapter"],
        versiculos=" ".join(state["verses"]),
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Execute the historical theological analysis"),
    ]
    response = model.invoke(messages)
    return {"historical_content": response.content}


def intertextual_node(state: TheologicalState):
    system_prompt = INTERTEXTUALITY_PROMPT.format(
        livro=state["bible_book"],
        capitulo=state["chapter"],
        versiculos=" ".join(state["verses"]),
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Execute intertextuality analysis"),
    ]
    response = model.invoke(messages)
    return {"intertextual_content": response.content}


def theological_validator_node(state: TheologicalState):
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
    response = model.invoke(messages)
    return {"validation_content": response.content}


def synthesizer_node(state: TheologicalState):
    system_prompt = SYNTHETIZER_PROMPT.format(
        panorama_content=state.get("panorama_content") or "",
        lexical_content=state.get("lexical_content") or "",
        historical_content=state.get("historical_content") or "",
        intertextual_content=state.get("intertextual_content") or "",
        validation_content=state.get("validation_content") or "",
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Write the study based on the reports provided, in Brazilian Portuguese"),
    ]
    response = model.invoke(messages)
    return {"final_analysis": response.content}


def join_node(state: TheologicalState):
    # This node simply acts as a synchronization point.
    # It doesn't need to do logic, just exist to accept edges.
    return state


def should_continue(state: TheologicalState) -> Literal["theological_validator", END]:
    """Check if all required fields are present to proceed."""
    required_fields = ["intertextual_content"]
    if "panorama" in state["selected_modules"]:
        required_fields.append("panorama_content")
    if "exegese" in state["selected_modules"]:
        required_fields.append("lexical_content")
    if "historical" in state["selected_modules"]:
        required_fields.append("historical_content")
    # Check if all required fields are populated
    # Note: State updates in LangGraph are merged.
    # If a field is missing, it means that parallel branch hasn't finished yet.
    for field in required_fields:
        if not state.get(field):
            return END  # Branch ends here; wait for last branch to finish.
    # If all fields are present, this is the last branch merging -> Proceed.
    return "theological_validator"
