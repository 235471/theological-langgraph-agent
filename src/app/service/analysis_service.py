"""
Analysis Service Layer

Handles the business logic for theological text analysis,
including state preparation and agent execution.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.agent.build import build_graph
from app.agent.agentState import TheologicalState


# Module name mapping from API to agent internal names
MODULE_MAPPING = {
    "panorama": "panorama",
    "exegese": "exegese",  # maps to lexical_agent
    "teologia": "historical",  # maps to historical_agent (teologia histórica)
}


@dataclass
class AnalysisInput:
    """Input data for theological analysis."""

    book: str
    chapter: int
    verses: List[int]
    selected_modules: List[str]


@dataclass
class AnalysisResult:
    """Result of theological analysis."""

    final_analysis: str
    success: bool
    error: Optional[str] = None


def prepare_agent_state(input_data: AnalysisInput) -> TheologicalState:
    """
    Prepare the initial state for the LangGraph agent.

    Args:
        input_data: Validated input from the API request

    Returns:
        TheologicalState dictionary ready for agent execution
    """
    # Map API module names to agent's internal module names
    agent_modules = [MODULE_MAPPING.get(m, m) for m in input_data.selected_modules]

    initial_state: TheologicalState = {
        "bible_book": input_data.book,
        "chapter": input_data.chapter,
        "verses": [str(v) for v in input_data.verses],  # Agent expects string list
        "selected_modules": agent_modules,
        # Initialize output fields as None
        "panorama_content": None,
        "lexical_content": None,
        "historical_content": None,
        "intertextual_content": None,
        "validation_content": None,
        "final_analysis": None,
    }

    return initial_state


def run_analysis(input_data: AnalysisInput) -> AnalysisResult:
    """
    Execute the theological analysis using the LangGraph multi-agent system.

    Args:
        input_data: Validated input containing book, chapter, verses, and modules

    Returns:
        AnalysisResult with the final analysis text or error information
    """
    try:
        # Prepare the initial state
        initial_state = prepare_agent_state(input_data)

        # Build and compile the graph
        graph = build_graph()

        # Execute the agent graph
        result = graph.invoke(initial_state)

        # Extract the final analysis
        final_analysis_data = result.get("final_analysis")

        if not final_analysis_data:
            return AnalysisResult(
                final_analysis="",
                success=False,
                error="Agent completed but did not produce a final analysis.",
            )

        # Handle structured output (dict or object with 'content' attribute)
        if isinstance(final_analysis_data, dict):
            final_analysis = final_analysis_data.get(
                "content", str(final_analysis_data)
            )
        elif hasattr(final_analysis_data, "content"):
            final_analysis = final_analysis_data.content
        else:
            final_analysis = str(final_analysis_data)

        return AnalysisResult(final_analysis=final_analysis, success=True)

    except Exception as e:
        return AnalysisResult(final_analysis="", success=False, error=str(e))


def format_verse_reference(book: str, chapter: int, verses: List[int]) -> str:
    """
    Format a verse reference string (e.g., "Sl 23:1-3" or "Sl 23:1,3,5").

    Args:
        book: Book abbreviation
        chapter: Chapter number
        verses: List of verse numbers

    Returns:
        Formatted reference string
    """
    if not verses:
        return f"{book} {chapter}"

    # Check if verses are consecutive
    verses_sorted = sorted(verses)
    if verses_sorted == list(range(verses_sorted[0], verses_sorted[-1] + 1)):
        # Consecutive range
        if len(verses_sorted) == 1:
            return f"{book} {chapter}:{verses_sorted[0]}"
        return f"{book} {chapter}:{verses_sorted[0]}-{verses_sorted[-1]}"
    else:
        # Non-consecutive, list them
        return f"{book} {chapter}:{','.join(map(str, verses_sorted))}"
