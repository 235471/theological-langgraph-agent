"""
Analysis Controller

Thin controller layer that handles HTTP concerns and delegates
business logic to the analysis service.
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.concurrency import run_in_threadpool

from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.service.bible_service import get_book_by_abbrev
from app.service.analysis_service import (
    AnalysisInput,
    run_analysis,
)
from app.service.trace_service import export_graph_trace

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Analysis"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze biblical text",
    description="Sends selected verses to the theological agent for multi-module analysis.",
)
async def analyze_text(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Analyze biblical text using the theological multi-agent system.

    - **book**: Book abbreviation (e.g., "Sl" for Psalms)
    - **chapter**: Chapter number (1-indexed)
    - **verses**: List of verse numbers to analyze
    - **selected_modules**: List of modules to run. Options: "panorama", "exegese", "teologia"

    For "Full" mode, send all modules: ["panorama", "exegese", "teologia"]
    For "Custom" mode, send at least one module.

    Returns governance metadata alongside the analysis result.
    """
    # --- Validation Layer ---
    book = get_book_by_abbrev(request.book)
    if not book:
        raise HTTPException(
            status_code=404,
            detail=f"Book with abbreviation '{request.book}' not found",
        )

    total_chapters = len(book.get("chapters", []))
    if request.chapter < 1 or request.chapter > total_chapters:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid chapter {request.chapter}. Book has {total_chapters} chapters.",
        )

    # --- Service Layer Delegation ---
    input_data = AnalysisInput(
        book=request.book,
        chapter=request.chapter,
        verses=request.verses,
        selected_modules=request.selected_modules,
    )

    try:
        result = await run_in_threadpool(run_analysis, input_data)
    except Exception as e:
        import traceback

        error_msg = f"Analysis failed: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {str(e)}",
        )

    # --- Response Handling ---
    if not result.success:
        if result.run_id and result.langsmith_run_id:
            await run_in_threadpool(
                export_graph_trace,
                result.run_id,
                result.langsmith_run_id,
            )
        logger.error(f"Analysis returned failure: {result.error}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {result.error}",
        )

    if not result.from_cache and result.run_id and result.langsmith_run_id:
        background_tasks.add_task(
            export_graph_trace,
            result.run_id,
            result.langsmith_run_id,
        )

    # HITL pending — return 202 Accepted with governance info
    if result.hitl_status == "pending":
        return AnalyzeResponse(
            final_analysis="⚠️ Análise pendente de revisão humana (HITL). "
            "O validador teológico identificou riscos graves. "
            f"Run ID: {result.run_id}",
            from_cache=False,
            run_id=result.run_id,
            tokens_consumed=result.tokens_consumed,
            model_versions=result.model_versions,
            prompt_versions=result.prompt_versions,
            risk_level=result.risk_level,
            hitl_status="pending",
        )

    return AnalyzeResponse(
        final_analysis=result.final_analysis,
        from_cache=result.from_cache,
        run_id=result.run_id,
        tokens_consumed=result.tokens_consumed,
        model_versions=result.model_versions,
        prompt_versions=result.prompt_versions,
        risk_level=result.risk_level,
        hitl_status=result.hitl_status,
    )
