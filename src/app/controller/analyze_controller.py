from fastapi import APIRouter, HTTPException
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.service.bible_service import get_book_by_abbrev, get_specific_verses

# Import the agent builder (uncomment when agent is ready)
# from app.agent.build import build_graph

router = APIRouter(tags=["Analysis"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze biblical text",
    description="Sends selected verses to the theological agent for multi-module analysis.",
)
async def analyze_text(request: AnalyzeRequest):
    """
    Analyze biblical text using the theological multi-agent system.

    - **book**: Book abbreviation (e.g., "Sl" for Psalms)
    - **chapter**: Chapter number (1-indexed)
    - **verses**: List of verse numbers to analyze
    - **selected_modules**: List of modules to run. Options: "panorama", "exegese", "teologia"

    For "Full" mode, send all modules: ["panorama", "exegese", "teologia"]
    For "Custom" mode, send at least one module.
    """
    # Validate book exists
    book = get_book_by_abbrev(request.book)
    if not book:
        raise HTTPException(
            status_code=404, detail=f"Book with abbreviation '{request.book}' not found"
        )

    # Validate chapter exists
    total_chapters = len(book.get("chapters", []))
    if request.chapter < 1 or request.chapter > total_chapters:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid chapter {request.chapter}. Book has {total_chapters} chapters.",
        )

    # Get the actual verse texts for context
    verse_texts = get_specific_verses(request.book, request.chapter, request.verses)

    if not verse_texts:
        raise HTTPException(
            status_code=400, detail="No valid verses found for the given verse numbers."
        )

    # Prepare state for the agent
    # Map input module names to agent's expected module names
    module_mapping = {
        "panorama": "panorama",
        "exegese": "exegese",  # maps to lexical_agent
        "teologia": "historical",  # maps to historical_agent (teologia histórica)
    }

    agent_modules = [module_mapping.get(m, m) for m in request.selected_modules]

    initial_state = {
        "bible_book": request.book,
        "chapter": request.chapter,
        "verses": [str(v) for v in request.verses],  # Agent expects string list
        "selected_modules": agent_modules,
        # Initialize output fields
        "panorama_content": None,
        "lexical_content": None,
        "historical_content": None,
        "intertextual_content": None,
        "validation_content": None,
        "final_analysis": None,
    }

    try:
        # Build and run the graph
        # graph = build_graph()
        # result = graph.invoke(initial_state)
        # final_analysis = result.get("final_analysis", "Analysis could not be completed.")

        # --- MOCK RESPONSE FOR TESTING (remove when agent is connected) ---
        final_analysis = f"""
# Análise Teológica: {request.book.upper()} {request.chapter}:{request.verses}

**Módulos Executados:** {', '.join(request.selected_modules)}

---

## Resumo

Esta é uma resposta de placeholder. O agente LangGraph ainda não está conectado.

**Versículos analisados:**

{chr(10).join([f'- Versículo {i+1}: "{text}"' for i, text in enumerate(verse_texts)])}

---

*Conecte o agente em `analyze_controller.py` para habilitar a análise real.*
"""
        # --- END MOCK ---

        return AnalyzeResponse(final_analysis=final_analysis)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
