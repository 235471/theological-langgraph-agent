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
