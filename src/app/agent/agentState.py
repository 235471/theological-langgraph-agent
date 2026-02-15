from typing import TypedDict, Optional, List


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
    model_versions: Optional[dict]  # {"panorama": "gemini-2.5-flash", ...}
    tokens_consumed: Optional[dict]  # {"panorama": {"input": N, "output": M}, ...}
    reasoning_steps: Optional[list]  # Zero-cost metadata from existing calls
    risk_level: Optional[str]  # "low" | "medium" | "high" — set by validator
    hitl_status: Optional[str]  # None | "pending" | "approved" | "edited"
