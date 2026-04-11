"""
Analysis Controller

Thin controller layer that handles HTTP concerns and delegates
business logic to the analysis service.
"""

import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.service.bible_service import get_book_by_abbrev
from app.service.analysis_service import (
    AnalysisInput,
    run_analysis,
    stream_analysis,
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
    - **selected_modules**: List of modules to run. Options: "panorama", "exegese", "historical"

    For "Full" mode, send all modules: ["panorama", "exegese", "historical"]
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


@router.post(
    "/analyze/stream",
    summary="Analyze biblical text (streaming)",
    description=(
        "Streams NDJSON progress events as the theological multi-agent graph executes. "
        "Each line is a valid JSON object. "
        "Event types: stage_start | node_complete | complete | cache_hit | error."
    ),
)
async def stream_analyze_text(request: AnalyzeRequest):
    """
    Streaming version of /analyze.

    Emits newline-delimited JSON (NDJSON) as each stage/node completes.
    The final event (type 'complete' or 'cache_hit') carries the full result.

    The sync generator (stream_analysis) is run in a thread-pool executor
    and events are piped through an asyncio.Queue to bridge the
    sync → async boundary without blocking the event loop.
    """
    # --- Validation (identical to /analyze) ---
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

    input_data = AnalysisInput(
        book=request.book,
        chapter=request.chapter,
        verses=request.verses,
        selected_modules=request.selected_modules,
    )

    # --- Async ↔ Sync bridge via asyncio.Queue ---
    # graph.stream() is synchronous; we run it in a thread-pool executor and
    # pipe events through a queue so FastAPI's async generator can yield them.
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def _run_sync():
        try:
            for event in stream_analysis(input_data):
                loop.call_soon_threadsafe(q.put_nowait, event)
        except Exception as exc:
            loop.call_soon_threadsafe(
                q.put_nowait, {"event": "error", "error": str(exc)}
            )
        finally:
            loop.call_soon_threadsafe(q.put_nowait, None)  # sentinel

    loop.run_in_executor(None, _run_sync)

    async def _async_generator():
        while True:
            event = await q.get()
            if event is None:
                break
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(
        _async_generator(),
        media_type="application/x-ndjson",
        headers={
            # Prevent nginx / Cloudflare from buffering chunks
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )
