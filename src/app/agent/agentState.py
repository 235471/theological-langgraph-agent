from typing import TypedDict, Optional, List, Annotated


def _merge_dicts(left: dict | None, right: dict | None) -> dict:
    """Reducer: merge two dicts (parallel nodes each contribute their key)."""
    return {**(left or {}), **(right or {})}


def _concat_lists(left: list | None, right: list | None) -> list:
    """Reducer: concatenate lists (parallel nodes each append their entry)."""
    return (left or []) + (right or [])


class TheologicalState(TypedDict):
    # Inputs
    bible_book: str
    chapter: int
    verses: List[str]
    selected_modules: List[str]

    # Outputs intermediários
    panorama_content: Optional[str]
    lexical_content: Optional[str]
    historical_content: Optional[str]
    intertextual_content: Optional[str]

    # Validação
    validation_content: Optional[str]

    # Output final
    final_analysis: Optional[str]

    # Governance / Observability
    run_id: Optional[str]
    created_at: Optional[str]
    model_versions: Annotated[
        dict, _merge_dicts
    ]  # {"panorama": "gemini-2.5-flash", ...}
    tokens_consumed: Annotated[
        dict, _merge_dicts
    ]  # {"panorama": {"input": N, "output": M}, ...}
    reasoning_steps: Annotated[
        list, _concat_lists
    ]  # Zero-cost metadata from existing calls
    risk_level: Optional[str]  # "low" | "medium" | "high" — set by validator
    hitl_status: Optional[str]  # None | "pending" | "approved" | "edited"
