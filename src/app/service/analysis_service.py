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
import threading
from datetime import datetime, timezone
from typing import List, Optional, Generator
from dataclasses import dataclass

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
    "exegese": "exegese",   # maps to lexical_agent
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
    langsmith_run_id: Optional[str] = None
    tokens_consumed: Optional[dict] = None
    model_versions: Optional[dict] = None
    prompt_versions: Optional[dict] = None
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
        "prompt_versions": {},
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
                langsmith_run_id=None,
                duration_ms=duration_ms,
            )
    except Exception as e:
        logger.warning(f"Cache check failed, proceeding without cache: {e}")

    # --- Agent Execution ---
    langsmith_run_id = str(uuid.uuid4())
    try:
        initial_state = prepare_agent_state(input_data, run_id)
        graph = build_graph()
        result = graph.invoke(
            initial_state,
            config={
                "run_id": uuid.UUID(langsmith_run_id),
                "run_name": "theological_analysis_graph",
                "metadata": {
                    "app_run_id": run_id,
                    "book": input_data.book,
                    "chapter": input_data.chapter,
                },
                "tags": ["analysis", "theological-agent"],
            },
        )
        duration_ms = int((time.time() - start_time) * 1000)

        # Extract governance metadata from result
        tokens_consumed = result.get("tokens_consumed")
        model_versions = result.get("model_versions")
        prompt_versions = result.get("prompt_versions")
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
                prompt_versions=prompt_versions,
                tokens_consumed=tokens_consumed,
                reasoning_steps=reasoning_steps,
                duration_ms=duration_ms,
            )
            return AnalysisResult(
                final_analysis="",
                success=True,
                run_id=run_id,
                langsmith_run_id=langsmith_run_id,
                tokens_consumed=tokens_consumed,
                model_versions=model_versions,
                prompt_versions=prompt_versions,
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
                prompt_versions=prompt_versions,
                tokens_consumed=tokens_consumed,
                reasoning_steps=reasoning_steps,
                duration_ms=duration_ms,
            )
            return AnalysisResult(
                final_analysis="",
                success=False,
                error="Agent completed but did not produce a final analysis.",
                run_id=run_id,
                langsmith_run_id=langsmith_run_id,
                tokens_consumed=tokens_consumed,
                model_versions=model_versions,
                prompt_versions=prompt_versions,
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
            prompt_versions=prompt_versions,
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
            langsmith_run_id=langsmith_run_id,
            tokens_consumed=tokens_consumed,
            model_versions=model_versions,
            prompt_versions=prompt_versions,
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
            langsmith_run_id=langsmith_run_id,
            duration_ms=duration_ms,
        )


def stream_analysis(input_data: AnalysisInput) -> Generator[dict, None, None]:
    """
    Streaming counterpart to run_analysis.

    Uses graph.stream(stream_mode="updates") to yield lightweight progress
    events as each node completes, then a final "complete" (or "cache_hit")
    event with the full result payload.

    Yields dicts with key "event":
      - "cache_hit"    : analysis served from cache; includes final_analysis
      - "stage_start"  : entering a new execution stage (1, 2, or 3)
      - "node_complete": a graph node finished; includes node name + stage
      - "complete"     : graph finished; includes full result payload
      - "error"        : unrecoverable failure; includes error message

    Stage mapping:
      Stage 1 — Parallel agents  : panorama, lexical, historical, intertextual, join
      Stage 2 — Validator        : theological_validator, hitl_pending
      Stage 3 — Synthesizer      : synthesizer

    NOTE: stream_mode="updates" returns raw pre-reducer node output, so
    dict/list state fields must be accumulated manually here.
    """
    run_id = str(uuid.uuid4())
    start_time = time.time()

    # ─── Cache Check ──────────────────────────────────────────────────────────
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
            yield {
                "event": "cache_hit",
                "final_analysis": cached,
                "from_cache": True,
                "run_id": run_id,
            }
            return
    except Exception as e:
        logger.warning(f"Stream: cache check failed, proceeding without cache: {e}")

    # ─── Stage → node mapping ─────────────────────────────────────────────────
    STAGE_MAP = {
        "panorama_agent":        1,
        "lexical_agent":         1,
        "historical_agent":      1,
        "intertextual_agent":    1,
        "join":                  1,
        "theological_validator": 2,
        "hitl_pending":          2,
        "synthesizer":           3,
    }

    # ─── Agent Execution ──────────────────────────────────────────────────────
    langsmith_run_id = str(uuid.uuid4())
    initial_state = prepare_agent_state(input_data, run_id)
    graph_instance = build_graph()

    config = {
        "run_id": uuid.UUID(langsmith_run_id),
        "run_name": "theological_analysis_graph",
        "metadata": {
            "app_run_id": run_id,
            "book": input_data.book,
            "chapter": input_data.chapter,
        },
        "tags": ["analysis", "theological-agent"],
    }

    # Manually accumulate state because stream_mode="updates" yields
    # pre-reducer partial dicts/lists from each node (not the merged state).
    acc: dict = {
        "model_versions":  {},
        "tokens_consumed": {},
        "prompt_versions": {},
        "reasoning_steps": [],
        "risk_level":      None,
        "hitl_status":     None,
        "final_analysis":  None,
    }

    current_stage = 0

    try:
        for chunk in graph_instance.stream(initial_state, config=config, stream_mode="updates"):
            if not chunk:
                continue

            for node_name, node_update in chunk.items():
                if not isinstance(node_update, dict):
                    continue

                stage = STAGE_MAP.get(node_name, 1)

                # Emit stage_start on first node of each new stage
                if stage != current_stage:
                    current_stage = stage
                    yield {"event": "stage_start", "stage": stage}

                # Accumulate governance metadata (partial dict updates per node)
                for key in ("model_versions", "tokens_consumed", "prompt_versions"):
                    val = node_update.get(key)
                    if isinstance(val, dict):
                        acc[key].update(val)

                steps = node_update.get("reasoning_steps")
                if isinstance(steps, list):
                    acc["reasoning_steps"].extend(steps)

                for key in ("risk_level", "hitl_status", "final_analysis"):
                    val = node_update.get(key)
                    if val is not None:
                        acc[key] = val

                yield {"event": "node_complete", "node": node_name, "stage": stage}

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        logger.error(f"Stream: graph execution failed: {error_msg}")
        save_run(
            run_id=run_id,
            book=input_data.book,
            chapter=input_data.chapter,
            verses=input_data.verses,
            selected_modules=input_data.selected_modules,
            success=False,
            error=error_msg,
            duration_ms=duration_ms,
        )
        yield {"event": "error", "error": error_msg}
        return

    duration_ms = int((time.time() - start_time) * 1000)
    risk_level = acc["risk_level"]
    hitl_status = acc["hitl_status"]

    # ─── Resolve final_analysis content ──────────────────────────────────────
    final_analysis_data = acc["final_analysis"]
    if isinstance(final_analysis_data, dict):
        final_analysis = final_analysis_data.get("content", str(final_analysis_data))
    elif hasattr(final_analysis_data, "content"):
        final_analysis = final_analysis_data.content
    else:
        final_analysis = str(final_analysis_data) if final_analysis_data else ""

    if "\\n" in final_analysis:
        final_analysis = final_analysis.replace("\\n", "\n")

    # ─── Cache write ──────────────────────────────────────────────────────────
    if final_analysis and not hitl_status:
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
            logger.warning(f"Stream: cache write failed (non-critical): {e}")

    # ─── Audit ────────────────────────────────────────────────────────────────
    save_run(
        run_id=run_id,
        book=input_data.book,
        chapter=input_data.chapter,
        verses=input_data.verses,
        selected_modules=input_data.selected_modules,
        success=True,
        final_analysis=final_analysis if not hitl_status else None,
        model_versions=acc["model_versions"],
        prompt_versions=acc["prompt_versions"],
        tokens_consumed=acc["tokens_consumed"],
        reasoning_steps=acc["reasoning_steps"],
        risk_level=risk_level,
        hitl_status=hitl_status,
        duration_ms=duration_ms,
    )

    # ─── Trace export (fire-and-forget daemon thread) ─────────────────────────
    try:
        from app.service.trace_service import export_graph_trace
        threading.Thread(
            target=export_graph_trace,
            args=(run_id, langsmith_run_id),
            daemon=True,
        ).start()
    except Exception as e:
        logger.warning(f"Stream: trace export thread failed to start: {e}")

    # ─── Final event ──────────────────────────────────────────────────────────
    yield {
        "event": "complete",
        "final_analysis": final_analysis,
        "from_cache": False,
        "run_id": run_id,
        "tokens_consumed": acc["tokens_consumed"],
        "model_versions": acc["model_versions"],
        "prompt_versions": acc["prompt_versions"],
        "risk_level": risk_level,
        "hitl_status": hitl_status,
    }


