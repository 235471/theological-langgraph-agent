"""
HITL Controller

Endpoints for Human-in-the-Loop review management.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.schemas import HITLReviewResponse, HITLApproveRequest, AnalyzeResponse
from app.service.hitl_service import (
    get_pending_reviews,
    get_review,
    approve_review,
    get_validation_content_for_synthesis,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hitl", tags=["HITL"])


@router.get(
    "/pending",
    summary="List pending HITL reviews",
    description="Returns all analyses awaiting human review.",
)
async def list_pending_reviews():
    """List all analyses pending human theological review."""
    reviews = await run_in_threadpool(get_pending_reviews)
    return {"pending": reviews, "count": len(reviews)}


@router.get(
    "/{run_id}",
    response_model=HITLReviewResponse,
    summary="Get HITL review details",
    description="Returns full details of a pending HITL review including all analysis content.",
)
async def get_review_details(run_id: str):
    """Get full details of a specific HITL review."""
    review = await run_in_threadpool(get_review, run_id)
    if not review:
        raise HTTPException(
            status_code=404,
            detail=f"No HITL review found for run_id: {run_id}",
        )
    return review


@router.post(
    "/{run_id}/approve",
    response_model=AnalyzeResponse,
    summary="Approve HITL review and resume synthesis",
    description="Approves the analysis (optionally editing content) and runs the synthesizer.",
)
async def approve_and_synthesize(run_id: str, request: HITLApproveRequest = None):
    """
    Approve or edit a HITL review and resume the synthesis step.

    If `edited_content` is provided, it replaces the validation content
    before running the synthesizer. Otherwise, the original content is used.
    """
    # Get the review
    review = await run_in_threadpool(get_review, run_id)
    if not review:
        raise HTTPException(
            status_code=404,
            detail=f"No HITL review found for run_id: {run_id}",
        )

    if review["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Review already processed. Status: {review['status']}",
        )

    edited_content = request.edited_content if request else None

    # Approve the review
    success = await run_in_threadpool(approve_review, run_id, edited_content)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to approve the review.",
        )

    # Resume synthesis with the validated (or edited) content
    try:
        result = await run_in_threadpool(
            _run_synthesis_from_review, review, edited_content
        )
        return result
    except Exception as e:
        import traceback

        logger.error(f"Synthesis after HITL approval failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Synthesis failed: {str(e)}",
        )


def _run_synthesis_from_review(
    review: dict, edited_content: str = None
) -> AnalyzeResponse:
    """Run only the synthesizer step using saved HITL state."""
    import time
    from app.agent.build import synthesizer_node
    from app.agent.agentState import TheologicalState
    from app.service.audit_service import save_run

    validation_content = edited_content or review.get("validation_content", "")

    # Reconstruct the state for synthesizer
    state: TheologicalState = {
        "bible_book": review["book"],
        "chapter": review["chapter"],
        "verses": [str(v) for v in review.get("verses", [])],
        "selected_modules": review.get("selected_modules", []),
        "panorama_content": review.get("panorama_content"),
        "lexical_content": review.get("lexical_content"),
        "historical_content": review.get("historical_content"),
        "intertextual_content": review.get("intertextual_content"),
        "validation_content": validation_content,
        "final_analysis": None,
        "run_id": review["run_id"],
        "created_at": review.get("created_at"),
        "model_versions": review.get("model_versions") or {},
        "prompt_versions": review.get("prompt_versions") or {},
        "tokens_consumed": review.get("tokens_consumed") or {},
        "reasoning_steps": review.get("reasoning_steps") or [],
        "risk_level": review.get("risk_level"),
        "hitl_status": "edited" if edited_content else "approved",
    }

    start = time.time()
    result = synthesizer_node(state)
    duration_ms = int((time.time() - start) * 1000)

    final_analysis = result.get("final_analysis", "")
    hitl_status = "edited" if edited_content else "approved"

    # Audit the resumed synthesis
    save_run(
        run_id=review["run_id"],
        book=review["book"],
        chapter=review["chapter"],
        verses=review.get("verses", []),
        selected_modules=review.get("selected_modules", []),
        success=True,
        final_analysis=final_analysis,
        hitl_status=hitl_status,
        risk_level=review.get("risk_level"),
        model_versions=result.get("model_versions"),
        prompt_versions=result.get("prompt_versions"),
        tokens_consumed=result.get("tokens_consumed"),
        reasoning_steps=result.get("reasoning_steps"),
        duration_ms=duration_ms,
    )

    return AnalyzeResponse(
        final_analysis=final_analysis,
        from_cache=False,
        run_id=review["run_id"],
        tokens_consumed=result.get("tokens_consumed"),
        model_versions=result.get("model_versions"),
        prompt_versions=result.get("prompt_versions"),
        risk_level=review.get("risk_level"),
        hitl_status=hitl_status,
    )
