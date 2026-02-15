"""
Analysis Service Layer

Handles the business logic for theological text analysis:
- Cache check/write (avoid duplicate studies)
- Agent execution with run_id tracking
- Audit persistence (every run — success or failure)
- Governance metadata extraction
"""

import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from dataclasses import dataclass, field

from app.agent.build import build_graph
from app.agent.agentState import TheologicalState
from app.utils.logger import get_logger
from app.service.cache_service import (
    generate_cache_key,
    get_cached_analysis,
    save_to_cache,
)
from app.service.audit_service import save_run

logger = get_logger(__name__)

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
    """Result of theological analysis with governance metadata."""

    final_analysis: str
    success: bool
    error: Optional[str] = None
    from_cache: bool = False
    run_id: Optional[str] = None
    tokens_consumed: Optional[dict] = None
    model_versions: Optional[dict] = None
    risk_level: Optional[str] = None
    hitl_status: Optional[str] = None
    reasoning_steps: Optional[list] = None
    duration_ms: Optional[int] = None


def prepare_agent_state(input_data: AnalysisInput, run_id: str) -> TheologicalState:
    """
    Prepare the initial state for the LangGraph agent.

    Args:
        input_data: Validated input from the API request
        run_id: Unique identifier for this analysis run

    Returns:
        TheologicalState dictionary ready for agent execution
    """
    agent_modules = [MODULE_MAPPING.get(m, m) for m in input_data.selected_modules]

    initial_state: TheologicalState = {
        # Inputs
        "bible_book": input_data.book,
        "chapter": input_data.chapter,
        "verses": [str(v) for v in input_data.verses],
        "selected_modules": agent_modules,
        # Output fields
        "panorama_content": None,
        "lexical_content": None,
        "historical_content": None,
        "intertextual_content": None,
        "validation_content": None,
        "final_analysis": None,
        # Governance
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_versions": {},
        "tokens_consumed": {},
        "reasoning_steps": [],
        "risk_level": None,
        "hitl_status": None,
    }

    return initial_state


def run_analysis(input_data: AnalysisInput) -> AnalysisResult:
    """
    Execute the theological analysis with cache, audit, and governance.

    Flow:
    1. Check cache → return if hit
    2. Build and run graph
    3. Handle HITL pending state
    4. Save to cache (on success)
    5. Save audit record (always)
    """
    run_id = str(uuid.uuid4())
    start_time = time.time()

    # --- Cache Check ---
    cache_key = generate_cache_key(
        input_data.book,
        input_data.chapter,
        input_data.verses,
        input_data.selected_modules,
    )

    try:
        cached = get_cached_analysis(cache_key)
        if cached:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Returning cached analysis",
                extra={
                    "event": "cache_hit",
                    "run_id": run_id,
                    "duration_ms": duration_ms,
                },
            )
            # Audit the cache hit too
            save_run(
                run_id=run_id,
                book=input_data.book,
                chapter=input_data.chapter,
                verses=input_data.verses,
                selected_modules=input_data.selected_modules,
                success=True,
                final_analysis=cached,
                duration_ms=duration_ms,
            )
            return AnalysisResult(
                final_analysis=cached,
                success=True,
                from_cache=True,
                run_id=run_id,
                duration_ms=duration_ms,
            )
    except Exception as e:
        logger.warning(f"Cache check failed, proceeding without cache: {e}")

    # --- Agent Execution ---
    try:
        initial_state = prepare_agent_state(input_data, run_id)
        graph = build_graph()
        result = graph.invoke(initial_state)
        duration_ms = int((time.time() - start_time) * 1000)

        # Extract governance metadata from result
        tokens_consumed = result.get("tokens_consumed")
        model_versions = result.get("model_versions")
        reasoning_steps = result.get("reasoning_steps")
        risk_level = result.get("risk_level")
        hitl_status = result.get("hitl_status")

        # --- HITL Pending ---
        if hitl_status == "pending":
            logger.info(
                f"Analysis pending HITL review",
                extra={"event": "analysis_hitl_pending", "run_id": run_id},
            )
            # Audit the pending state
            save_run(
                run_id=run_id,
                book=input_data.book,
                chapter=input_data.chapter,
                verses=input_data.verses,
                selected_modules=input_data.selected_modules,
                success=True,
                hitl_status="pending",
                risk_level=risk_level,
                model_versions=model_versions,
                tokens_consumed=tokens_consumed,
                reasoning_steps=reasoning_steps,
                duration_ms=duration_ms,
            )
            return AnalysisResult(
                final_analysis="",
                success=True,
                run_id=run_id,
                tokens_consumed=tokens_consumed,
                model_versions=model_versions,
                risk_level=risk_level,
                hitl_status="pending",
                reasoning_steps=reasoning_steps,
                duration_ms=duration_ms,
            )

        # --- Extract final analysis ---
        final_analysis_data = result.get("final_analysis")

        if not final_analysis_data:
            save_run(
                run_id=run_id,
                book=input_data.book,
                chapter=input_data.chapter,
                verses=input_data.verses,
                selected_modules=input_data.selected_modules,
                success=False,
                error="Agent completed but did not produce a final analysis.",
                model_versions=model_versions,
                tokens_consumed=tokens_consumed,
                reasoning_steps=reasoning_steps,
                duration_ms=duration_ms,
            )
            return AnalysisResult(
                final_analysis="",
                success=False,
                error="Agent completed but did not produce a final analysis.",
                run_id=run_id,
                tokens_consumed=tokens_consumed,
                model_versions=model_versions,
            )

        # Handle structured output
        if isinstance(final_analysis_data, dict):
            final_analysis = final_analysis_data.get(
                "content", str(final_analysis_data)
            )
        elif hasattr(final_analysis_data, "content"):
            final_analysis = final_analysis_data.content
        else:
            final_analysis = str(final_analysis_data)

        # --- Save to cache ---
        try:
            save_to_cache(
                cache_key=cache_key,
                book=input_data.book,
                chapter=input_data.chapter,
                verses=input_data.verses,
                modules=input_data.selected_modules,
                final_analysis=final_analysis,
                run_id=run_id,
            )
        except Exception as e:
            logger.warning(f"Cache write failed (non-critical): {e}")

        # --- Audit ---
        save_run(
            run_id=run_id,
            book=input_data.book,
            chapter=input_data.chapter,
            verses=input_data.verses,
            selected_modules=input_data.selected_modules,
            success=True,
            final_analysis=final_analysis,
            model_versions=model_versions,
            tokens_consumed=tokens_consumed,
            reasoning_steps=reasoning_steps,
            risk_level=risk_level,
            hitl_status=hitl_status,
            duration_ms=duration_ms,
        )

        logger.info(
            f"Analysis completed successfully",
            extra={
                "event": "analysis_complete",
                "run_id": run_id,
                "duration_ms": duration_ms,
                "risk_level": risk_level,
            },
        )

        return AnalysisResult(
            final_analysis=final_analysis,
            success=True,
            run_id=run_id,
            tokens_consumed=tokens_consumed,
            model_versions=model_versions,
            risk_level=risk_level,
            hitl_status=hitl_status,
            reasoning_steps=reasoning_steps,
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        save_run(
            run_id=run_id,
            book=input_data.book,
            chapter=input_data.chapter,
            verses=input_data.verses,
            selected_modules=input_data.selected_modules,
            success=False,
            error=str(e),
            duration_ms=duration_ms,
        )
        return AnalysisResult(
            final_analysis="",
            success=False,
            error=str(e),
            run_id=run_id,
            duration_ms=duration_ms,
        )


def format_verse_reference(book: str, chapter: int, verses: List[int]) -> str:
    """
    Format a verse reference string (e.g., "Sl 23:1-3" or "Sl 23:1,3,5").
    """
    if not verses:
        return f"{book} {chapter}"

    verses_sorted = sorted(verses)
    if verses_sorted == list(range(verses_sorted[0], verses_sorted[-1] + 1)):
        if len(verses_sorted) == 1:
            return f"{book} {chapter}:{verses_sorted[0]}"
        return f"{book} {chapter}:{verses_sorted[0]}-{verses_sorted[-1]}"
    else:
        return f"{book} {chapter}:{','.join(map(str, verses_sorted))}"
